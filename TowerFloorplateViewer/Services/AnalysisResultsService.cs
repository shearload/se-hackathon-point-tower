using System.Globalization;
using System.IO;
using System.Linq;
using System.Text.Json;
using TowerFloorplateViewer.Models;

namespace TowerFloorplateViewer.Services;

public sealed class AnalysisResultsService
{
    private readonly FloorplateJsonService _floorplateJsonService = new();

    public async Task<AnalysisResultsPackage> LoadAsync(
        string path,
        CancellationToken cancellationToken = default)
    {
        var fullPath = Path.GetFullPath(path);
        var optimizerGeometry = await _floorplateJsonService.LoadAsync(fullPath);
        await using var stream = File.OpenRead(fullPath);
        using var json = await JsonDocument.ParseAsync(stream, cancellationToken: cancellationToken);
        var root = json.RootElement;

        if (!root.TryGetProperty("optimization_results", out var optimizationResults)
            || !optimizationResults.TryGetProperty("candidates", out var candidatesElement)
            || candidatesElement.ValueKind != JsonValueKind.Object)
        {
            throw new InvalidDataException("The results file must contain optimization_results.candidates.");
        }

        var candidates = candidatesElement.EnumerateObject()
            .Select(property => ParseCandidate(property.Name, property.Value))
            .ToArray();
        if (candidates.Length < 2)
            throw new InvalidDataException("The results file must contain the default candidate and at least one geometry alternative.");

        var caseNames = candidates[0].Cases.Keys.ToArray();
        if (caseNames.Length == 0)
            throw new InvalidDataException("The default candidate does not contain any analysis cases.");

        var optionTypes = ResolveOptionTypes(root, optimizerGeometry, candidates);
        var geometryOptions = new List<AnalysisGeometryOption>
        {
            new()
            {
                Id = candidates[0].Id,
                Label = "Default",
                IsDefault = true,
                Geometry = null,
                Cases = candidates[0].Cases
            }
        };

        for (var index = 1; index < candidates.Length; index++)
        {
            var candidate = candidates[index];
            var geometry = CreateCandidateGeometry(optimizerGeometry, candidate.OccupiedStories, optionTypes);
            geometryOptions.Add(new AnalysisGeometryOption
            {
                Id = candidate.Id,
                Label = candidate.Id,
                IsDefault = false,
                Geometry = geometry,
                Cases = candidate.Cases
            });
        }

        return new AnalysisResultsPackage
        {
            SourcePath = fullPath,
            CaseNames = caseNames.ToList(),
            GeometryOptions = geometryOptions
        };
    }

    private static ParsedCandidate ParseCandidate(string propertyName, JsonElement candidate)
    {
        var id = candidate.TryGetProperty("candidate_id", out var idElement) && idElement.ValueKind == JsonValueKind.String
            ? idElement.GetString()!
            : propertyName;

        var occupiedStories = candidate.TryGetProperty("occupied_stories", out var storiesElement)
            && storiesElement.ValueKind == JsonValueKind.Array
                ? storiesElement.EnumerateArray()
                    .Where(item => item.ValueKind == JsonValueKind.Number && item.TryGetInt32(out _))
                    .Select(item => item.GetInt32())
                    .ToHashSet()
                : new HashSet<int>();

        var cases = new Dictionary<string, List<FloorAnalysisResult>>(StringComparer.OrdinalIgnoreCase);
        if (candidate.TryGetProperty("cases", out var casesElement) && casesElement.ValueKind == JsonValueKind.Object)
        {
            foreach (var caseProperty in casesElement.EnumerateObject())
            {
                if (!caseProperty.Value.TryGetProperty("floors", out var floorsElement)) continue;
                var floors = new List<FloorAnalysisResult>();
                if (floorsElement.ValueKind == JsonValueKind.Object)
                {
                    foreach (var floorProperty in floorsElement.EnumerateObject())
                        floors.Add(ParseFloor(floorProperty.Value, floorProperty.Name, floors.Count + 1));
                }
                else if (floorsElement.ValueKind == JsonValueKind.Array)
                {
                    foreach (var floor in floorsElement.EnumerateArray())
                        floors.Add(ParseFloor(floor, null, floors.Count + 1));
                }
                if (floors.Count > 0) cases[caseProperty.Name] = floors.OrderBy(floor => floor.FloorNumber).ToList();
            }
        }

        return new ParsedCandidate(id, occupiedStories, cases);
    }

    private static FloorAnalysisResult ParseFloor(JsonElement floor, string? key, int fallbackNumber)
    {
        var number = TryGetInt(floor, "floor_number")
            ?? (int.TryParse(key, NumberStyles.Integer, CultureInfo.InvariantCulture, out var parsedKey) ? parsedKey + 1 : fallbackNumber);
        return new FloorAnalysisResult
        {
            FloorNumber = number,
            ElevationFt = GetNumber(floor, "elevation_ft"),
            UxIn = GetNumber(floor, "ux_in"),
            UyIn = GetNumber(floor, "uy_in"),
            RzRad = GetNumber(floor, "rz_rad"),
            MaxDriftResultant = GetOptionalNumber(floor, "max_drift_resultant"),
            DisplacementResultantIn = GetOptionalNumber(floor, "displacement_resultant_in"),
            MaxStoryDisplacementResultantIn = GetOptionalNumber(floor, "max_story_displacement_resultant_in")
        };
    }

    private static List<string> ResolveOptionTypes(JsonElement root, FloorplateDocument model, IReadOnlyList<ParsedCandidate> candidates)
    {
        if (model.FloorSequence.Count == 0) return new List<string>();
        var selectedCandidateId = root.TryGetProperty("optimization_results", out var results)
            && results.TryGetProperty("model_candidate_id", out var modelCandidateElement)
                ? modelCandidateElement.GetString()
                : null;
        var selectedCandidate = candidates.FirstOrDefault(candidate => string.Equals(candidate.Id, selectedCandidateId, StringComparison.OrdinalIgnoreCase))
            ?? candidates.FirstOrDefault(candidate => candidate.OccupiedStories.Count > 0);
        if (selectedCandidate is null) return model.FloorSequence.Select(entry => entry.Type).Distinct(StringComparer.Ordinal).ToList();

        var occupiedTypes = selectedCandidate.OccupiedStories
            .Where(story => story >= 1 && story <= model.FloorSequence.Count)
            .Select(story => model.FloorSequence[story - 1].Type)
            .GroupBy(type => type, StringComparer.Ordinal)
            .OrderByDescending(group => group.Count())
            .Select(group => group.Key)
            .FirstOrDefault();
        if (occupiedTypes is null) return model.FloorSequence.Select(entry => entry.Type).Distinct(StringComparer.Ordinal).ToList();

        var baselineType = model.FloorSequence
            .Where((_, index) => !selectedCandidate.OccupiedStories.Contains(index + 1))
            .GroupBy(entry => entry.Type, StringComparer.Ordinal)
            .OrderByDescending(group => group.Count())
            .Select(group => group.Key)
            .FirstOrDefault();
        baselineType ??= model.FloorSequence[0].Type;
        return new List<string> { baselineType, occupiedTypes };
    }

    private static FloorplateDocument CreateCandidateGeometry(
        FloorplateDocument optimizerModel,
        HashSet<int> occupiedStories,
        IReadOnlyList<string> optionTypes)
    {
        if (occupiedStories.Count == 0 || optionTypes.Count < 2)
            return optimizerModel;

        var baselineType = optionTypes[0];
        var optionType = optionTypes[1];
        var sequence = optimizerModel.FloorSequence
            .Select((entry, index) => new FloorSequenceEntry
            {
                Type = occupiedStories.Contains(index + 1) ? optionType : baselineType,
                FloorHeight = entry.FloorHeight
            })
            .ToList();

        return new FloorplateDocument
        {
            FormatVersion = optimizerModel.FormatVersion,
            Units = optimizerModel.Units,
            FloorSequence = sequence,
            FloorTypes = optimizerModel.FloorTypes
        };
    }

    private static int? TryGetInt(JsonElement obj, string propertyName)
    {
        return obj.TryGetProperty(propertyName, out var value) && value.TryGetInt32(out var number) ? number : null;
    }

    private static double GetNumber(JsonElement obj, string propertyName)
    {
        return GetOptionalNumber(obj, propertyName) ?? 0;
    }

    private static double? GetOptionalNumber(JsonElement obj, string propertyName)
    {
        return obj.TryGetProperty(propertyName, out var value) && value.ValueKind == JsonValueKind.Number && value.TryGetDouble(out var number)
            ? number
            : null;
    }

    private sealed record ParsedCandidate(string Id, HashSet<int> OccupiedStories, Dictionary<string, List<FloorAnalysisResult>> Cases);
}
