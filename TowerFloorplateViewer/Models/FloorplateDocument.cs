using System.Text.Json.Serialization;

namespace TowerFloorplateViewer.Models;

public sealed class FloorplateDocument
{
    [JsonPropertyName("format_version")] public string FormatVersion { get; init; } = "";
    [JsonPropertyName("units")] public Dictionary<string, string> Units { get; init; } = new();
    [JsonPropertyName("floor_sequence")] public List<FloorSequenceEntry> FloorSequence { get; init; } = new();
    [JsonPropertyName("floor_types")] public Dictionary<string, FloorType> FloorTypes { get; init; } = new();
}

public sealed class FloorSequenceEntry
{
    [JsonPropertyName("type")] public string Type { get; init; } = "";
    [JsonPropertyName("floor_height")] public double FloorHeight { get; init; }
}

public sealed class FloorType
{
    [JsonPropertyName("structural_nodes")] public List<StructuralNode> StructuralNodes { get; init; } = new();
    [JsonPropertyName("structural_elements")] public List<StructuralElement> StructuralElements { get; init; } = new();
    [JsonPropertyName("floor_plate")] public FloorPlate FloorPlate { get; init; } = new();
}

public sealed class StructuralNode
{
    [JsonPropertyName("id")] public string Id { get; init; } = "";
    [JsonPropertyName("x")] public double X { get; init; }
    [JsonPropertyName("y")] public double Y { get; init; }
}

public sealed class StructuralElement
{
    [JsonPropertyName("id")] public string Id { get; init; } = "";
    [JsonPropertyName("type")] public string Type { get; init; } = "";
    [JsonPropertyName("nodes")] public List<string> Nodes { get; init; } = new();
    [JsonPropertyName("material_name")] public string MaterialName { get; init; } = "";
    [JsonPropertyName("section_name")] public string SectionName { get; init; } = "";
    [JsonPropertyName("Fy")] public double Fy { get; init; }
    [JsonPropertyName("E")] public double E { get; init; }
    [JsonPropertyName("poisson_ratio")] public double PoissonRatio { get; init; }
    [JsonPropertyName("section_dims")] public SectionDimensions SectionDims { get; init; } = new();
}

public sealed class SectionDimensions
{
    [JsonPropertyName("width")] public double Width { get; init; }
    [JsonPropertyName("depth")] public double Depth { get; init; }
}

public sealed class FloorPlate
{
    [JsonPropertyName("boundary_nodes")] public List<BoundaryNode> BoundaryNodes { get; init; } = new();
    [JsonPropertyName("boundary_loop")] public List<string> BoundaryLoop { get; init; } = new();
}

public sealed class BoundaryNode
{
    [JsonPropertyName("id")] public string Id { get; init; } = "";
    [JsonPropertyName("x")] public double X { get; init; }
    [JsonPropertyName("y")] public double Y { get; init; }
}
