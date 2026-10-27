using System.Text.Json.Serialization;

namespace TowerFloorplateViewer.Models;

public sealed class LoadModuleOutput
{
    [JsonPropertyName("story_forces_kip")] public Dictionary<string, double> StoryForcesKip { get; init; } = new();
}

public sealed class StoryForceLoad
{
    [JsonPropertyName("floor_number")] public int FloorNumber { get; init; }
    [JsonPropertyName("x")] public double X { get; init; }
    [JsonPropertyName("y")] public double Y { get; init; }
    [JsonPropertyName("z")] public double Z { get; init; }
    [JsonPropertyName("force_kip")] public double ForceKip { get; init; }
}
