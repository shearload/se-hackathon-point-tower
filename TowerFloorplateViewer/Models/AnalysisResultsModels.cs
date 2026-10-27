using System.Text.Json.Serialization;

namespace TowerFloorplateViewer.Models;

public sealed class AnalysisResultsPackage
{
    public string SourcePath { get; init; } = "";
    public List<string> CaseNames { get; init; } = new();
    public List<AnalysisGeometryOption> GeometryOptions { get; init; } = new();
}

public sealed class AnalysisGeometryOption
{
    [JsonPropertyName("id")] public string Id { get; init; } = "";
    [JsonPropertyName("label")] public string Label { get; init; } = "";
    [JsonPropertyName("isDefault")] public bool IsDefault { get; init; }
    [JsonPropertyName("geometry")] public FloorplateDocument? Geometry { get; init; }
    [JsonPropertyName("cases")] public Dictionary<string, List<FloorAnalysisResult>> Cases { get; init; } = new();
}

public sealed class FloorAnalysisResult
{
    [JsonPropertyName("floor_number")] public int FloorNumber { get; init; }
    [JsonPropertyName("elevation_ft")] public double ElevationFt { get; init; }
    [JsonPropertyName("ux_in")] public double UxIn { get; init; }
    [JsonPropertyName("uy_in")] public double UyIn { get; init; }
    [JsonPropertyName("rz_rad")] public double RzRad { get; init; }
    [JsonPropertyName("max_drift_resultant")] public double? MaxDriftResultant { get; init; }
    [JsonPropertyName("displacement_resultant_in")] public double? DisplacementResultantIn { get; init; }
    [JsonPropertyName("max_story_displacement_resultant_in")] public double? MaxStoryDisplacementResultantIn { get; init; }
}
