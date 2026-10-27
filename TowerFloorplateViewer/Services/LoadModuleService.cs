using System.Diagnostics;
using System.IO;
using System.Text.Json;
using TowerFloorplateViewer.Models;

namespace TowerFloorplateViewer.Services;

public sealed class LoadModuleService
{
    private static readonly JsonSerializerOptions JsonOptions = new() { PropertyNameCaseInsensitive = false };

    public async Task<(IReadOnlyList<StoryForceLoad> Loads, string ForceUnit, string? Warning)> RunAsync(
        string executablePath,
        string inputJsonPath,
        FloorplateDocument floorplate,
        CancellationToken cancellationToken = default)
    {
        var forceUnit = floorplate.Units.TryGetValue("force", out var unit) && !string.IsNullOrWhiteSpace(unit) ? unit : "kip";
        if (!string.Equals(forceUnit, "kip", StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException($"The load module outputs kips but the floorplate declares '{forceUnit}'.");

        var startInfo = new ProcessStartInfo
        {
            FileName = executablePath,
            WorkingDirectory = Path.GetDirectoryName(executablePath)!,
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true
        };
        startInfo.ArgumentList.Add(Path.GetFullPath(inputJsonPath));

        using var process = new Process { StartInfo = startInfo };
        if (!process.Start()) throw new InvalidOperationException("The load module did not start.");

        var stdoutTask = process.StandardOutput.ReadToEndAsync(cancellationToken);
        var stderrTask = process.StandardError.ReadToEndAsync(cancellationToken);
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(TimeSpan.FromMinutes(5));
        try
        {
            await process.WaitForExitAsync(timeout.Token);
        }
        catch (OperationCanceledException)
        {
            try { process.Kill(entireProcessTree: true); } catch { /* Process may already have exited. */ }
            throw new TimeoutException("The load module exceeded its 5-minute run limit.");
        }

        var output = await stdoutTask;
        var errors = await stderrTask;
        if (process.ExitCode != 0)
            throw new InvalidOperationException(string.IsNullOrWhiteSpace(errors)
                ? $"The load module exited with code {process.ExitCode}."
                : $"The load module failed: {errors.Trim()}");
        if (string.IsNullOrWhiteSpace(output)) throw new InvalidDataException("The load module returned no JSON on standard output.");

        var jsonStart = output.IndexOf('{');
        var jsonEnd = output.LastIndexOf('}');
        if (jsonStart < 0 || jsonEnd < jsonStart) throw new InvalidDataException("The load module did not print a JSON object.");
        var warning = output[..jsonStart].Trim();
        var json = output[jsonStart..(jsonEnd + 1)];
        LoadModuleOutput result;
        try
        {
            result = JsonSerializer.Deserialize<LoadModuleOutput>(json, JsonOptions)
                ?? throw new InvalidDataException("The load module returned an empty JSON value.");
        }
        catch (JsonException ex)
        {
            throw new InvalidDataException("The load module must print JSON containing a 'story_forces_kip' mapping to standard output.", ex);
        }

        var resolved = new List<StoryForceLoad>(result.StoryForcesKip.Count);
        var skippedFloors = 0;
        foreach (var (storyText, forceKip) in result.StoryForcesKip)
        {
            if (!int.TryParse(storyText, out var storyNumber) || storyNumber < 1)
                throw new InvalidDataException($"Load output key '{storyText}' is not a 1-based floor number.");
            if (storyNumber > floorplate.FloorSequence.Count)
            {
                skippedFloors++;
                continue;
            }
            resolved.Add(ResolveStoryForce(storyNumber, forceKip, floorplate));
        }
        if (skippedFloors > 0)
            warning = string.Join(Environment.NewLine, new[] { warning, $"Skipped {skippedFloors} floor load(s) because the loaded floorplate has only {floorplate.FloorSequence.Count} floor(s)." }.Where(line => !string.IsNullOrWhiteSpace(line)));
        return (resolved, forceUnit, string.IsNullOrWhiteSpace(warning) ? null : warning);
    }

    private static StoryForceLoad ResolveStoryForce(int storyNumber, double forceKip, FloorplateDocument floorplate)
    {
        var entry = floorplate.FloorSequence[storyNumber - 1];
        var floorType = floorplate.FloorTypes[entry.Type];
        var boundaryById = floorType.FloorPlate.BoundaryNodes.ToDictionary(node => node.Id, StringComparer.Ordinal);
        var points = floorType.FloorPlate.BoundaryLoop.Select(id => boundaryById[id]).ToArray();
        double twiceArea = 0, centroidXNumerator = 0, centroidYNumerator = 0;
        for (var i = 0; i < points.Length; i++)
        {
            var next = points[(i + 1) % points.Length];
            var cross = points[i].X * next.Y - next.X * points[i].Y;
            twiceArea += cross;
            centroidXNumerator += (points[i].X + next.X) * cross;
            centroidYNumerator += (points[i].Y + next.Y) * cross;
        }
        if (Math.Abs(twiceArea) < 1e-9) throw new InvalidDataException($"Floor {storyNumber} has a floor plate with zero area.");
        var topZ = floorplate.FloorSequence.Take(storyNumber).Sum(floor => floor.FloorHeight);
        return new StoryForceLoad
        {
            FloorNumber = storyNumber,
            X = centroidXNumerator / (3 * twiceArea),
            Y = centroidYNumerator / (3 * twiceArea),
            Z = topZ,
            ForceKip = forceKip
        };
    }
}
