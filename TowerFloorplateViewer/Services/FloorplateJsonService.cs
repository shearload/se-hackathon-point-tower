using System.IO;
using System.Text.Json;
using TowerFloorplateViewer.Models;

namespace TowerFloorplateViewer.Services;

public sealed class FloorplateJsonService
{
    private static readonly JsonSerializerOptions Options = new() { PropertyNameCaseInsensitive = false, ReadCommentHandling = JsonCommentHandling.Skip };

    public async Task<FloorplateDocument> LoadAsync(string path)
    {
        await using var stream = File.OpenRead(path);
        var document = await JsonSerializer.DeserializeAsync<FloorplateDocument>(stream, Options)
            ?? throw new InvalidDataException("The JSON file is empty or does not match the floorplate format.");
        Validate(document);
        return document;
    }

    private static void Validate(FloorplateDocument document)
    {
        if (document.FloorTypes.Count == 0) throw new InvalidDataException("floor_types must define at least one floor type.");
        if (document.FloorSequence.Count == 0) throw new InvalidDataException("floor_sequence must contain at least one floor.");
        foreach (var (index, entry) in document.FloorSequence.Select((entry, index) => (index, entry)))
        {
            if (!document.FloorTypes.TryGetValue(entry.Type, out var floor)) throw new InvalidDataException($"Floor {index + 1} refers to undefined floor type '{entry.Type}'.");
            if (entry.FloorHeight <= 0) throw new InvalidDataException($"Floor {index + 1} must have a positive floor_height.");
            ValidateFloor(floor, entry.Type);
        }
    }

    private static void ValidateFloor(FloorType floor, string floorType)
    {
        var nodes = floor.StructuralNodes.ToDictionary(n => n.Id, StringComparer.Ordinal);
        if (nodes.Count != floor.StructuralNodes.Count) throw new InvalidDataException($"Floor type '{floorType}' contains duplicate structural node IDs.");
        foreach (var element in floor.StructuralElements)
        {
            var type = element.Type.ToLowerInvariant();
            if (type is not ("column" or "beam" or "shear_wall" or "outrigger"))
                throw new InvalidDataException($"Element '{element.Id}' has unsupported type '{element.Type}'.");
            var expected = type == "column" ? 1 : 2;
            if (element.Nodes.Count != expected) throw new InvalidDataException($"Element '{element.Id}' of type '{element.Type}' must reference {expected} node(s).");
            foreach (var id in element.Nodes)
                if (!nodes.ContainsKey(id)) throw new InvalidDataException($"Element '{element.Id}' references missing node '{id}'.");
            if (element.SectionDims.Width <= 0 || element.SectionDims.Depth <= 0) throw new InvalidDataException($"Element '{element.Id}' must have positive section dimensions.");
        }

        var boundary = floor.FloorPlate.BoundaryNodes.ToDictionary(n => n.Id, StringComparer.Ordinal);
        if (boundary.Count < 3 || boundary.Count != floor.FloorPlate.BoundaryNodes.Count) throw new InvalidDataException($"Floor type '{floorType}' needs at least three uniquely named floor plate boundary nodes.");
        if (floor.FloorPlate.BoundaryLoop.Count < 3 || floor.FloorPlate.BoundaryLoop.Any(id => !boundary.ContainsKey(id)))
            throw new InvalidDataException($"Floor type '{floorType}' has an invalid floor_plate.boundary_loop.");
    }
}
