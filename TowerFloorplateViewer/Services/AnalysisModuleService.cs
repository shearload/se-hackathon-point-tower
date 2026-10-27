using System.Diagnostics;
using System.IO;
using System.Text.Json;

namespace TowerFloorplateViewer.Services;

public sealed class AnalysisModuleService
{
    public async Task<(string ResultsPath, string? Note)> RunAsync(
        string executablePath,
        string buildingJsonPath,
        string loadsJsonPath,
        CancellationToken cancellationToken = default)
    {
        var outputDirectory = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "TowerFloorplateViewer",
            "AnalysisResults",
            DateTime.UtcNow.ToString("yyyyMMdd-HHmmss-fff"));
        Directory.CreateDirectory(outputDirectory);

        var startInfo = new ProcessStartInfo
        {
            FileName = executablePath,
            WorkingDirectory = Path.GetDirectoryName(executablePath)!,
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true
        };
        startInfo.ArgumentList.Add("analyze");
        startInfo.ArgumentList.Add("--input");
        startInfo.ArgumentList.Add(Path.GetFullPath(buildingJsonPath));
        startInfo.ArgumentList.Add("--loads");
        startInfo.ArgumentList.Add(Path.GetFullPath(loadsJsonPath));
        startInfo.ArgumentList.Add("--output");
        startInfo.ArgumentList.Add(outputDirectory);

        using var process = new Process { StartInfo = startInfo };
        if (!process.Start()) throw new InvalidOperationException("The analysis module did not start.");

        var stdoutTask = process.StandardOutput.ReadToEndAsync(cancellationToken);
        var stderrTask = process.StandardError.ReadToEndAsync(cancellationToken);
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(TimeSpan.FromMinutes(30));
        try
        {
            await process.WaitForExitAsync(timeout.Token);
        }
        catch (OperationCanceledException)
        {
            try { process.Kill(entireProcessTree: true); } catch { /* Process may already have exited. */ }
            throw new TimeoutException("The analysis module exceeded its 30-minute run limit.");
        }

        var output = await stdoutTask;
        var errors = await stderrTask;
        if (process.ExitCode != 0)
            throw new InvalidOperationException(string.IsNullOrWhiteSpace(errors)
                ? $"The analysis executable exited with code {process.ExitCode}."
                : $"The analysis executable failed: {errors.Trim()}");

        var resultLine = output.Split(new[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries)
            .Select(line => line.Trim())
            .LastOrDefault(line => !string.IsNullOrWhiteSpace(line));
        var printedPath = resultLine;
        if (!string.IsNullOrWhiteSpace(printedPath))
        {
            foreach (var prefix in new[] { "RESULTS_PATH=", "Results file:", "Output file:" })
                if (printedPath.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
                {
                    printedPath = printedPath[prefix.Length..].Trim();
                    break;
                }
            printedPath = printedPath.Trim('"');
            foreach (var candidatePath in new[]
            {
                Path.IsPathRooted(printedPath) ? Path.GetFullPath(printedPath) : Path.GetFullPath(printedPath, outputDirectory),
                Path.IsPathRooted(printedPath) ? Path.GetFullPath(printedPath) : Path.GetFullPath(printedPath, Path.GetDirectoryName(executablePath)!)
            })
                if (File.Exists(candidatePath)) return (candidatePath, string.IsNullOrWhiteSpace(errors) ? null : errors.Trim());
        }

        var discoveredResults = await FindResultsJsonAsync(outputDirectory, cancellationToken);
        if (discoveredResults is not null)
            return (discoveredResults, string.IsNullOrWhiteSpace(errors) ? null : errors.Trim());

        var details = string.IsNullOrWhiteSpace(errors) ? output.Trim() : errors.Trim();
        throw new InvalidDataException(string.IsNullOrWhiteSpace(details)
            ? $"Analysis.exe completed without producing a results JSON in '{outputDirectory}'."
            : $"Analysis.exe did not produce a readable results path. Output: {details}");
    }

    private static async Task<string?> FindResultsJsonAsync(string outputDirectory, CancellationToken cancellationToken)
    {
        foreach (var path in Directory.EnumerateFiles(outputDirectory, "*.json", SearchOption.AllDirectories)
                     .OrderByDescending(File.GetLastWriteTimeUtc))
        {
            try
            {
                await using var stream = File.OpenRead(path);
                using var json = await JsonDocument.ParseAsync(stream, cancellationToken: cancellationToken);
                if (json.RootElement.TryGetProperty("optimization_results", out var results)
                    && results.TryGetProperty("candidates", out _))
                    return path;
            }
            catch (JsonException)
            {
                // Ignore auxiliary JSON files that are not analysis result documents.
            }
        }
        return null;
    }
}
