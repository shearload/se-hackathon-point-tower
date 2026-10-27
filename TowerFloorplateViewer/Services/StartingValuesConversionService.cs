using System.Diagnostics;
using System.IO;

namespace TowerFloorplateViewer.Services;

public sealed class StartingValuesConversionService
{
    public async Task<string> ConvertAsync(
        string executablePath,
        string csvPath,
        CancellationToken cancellationToken = default)
    {
        var fullCsvPath = Path.GetFullPath(csvPath);
        var startInfo = new ProcessStartInfo
        {
            FileName = executablePath,
            WorkingDirectory = Path.GetDirectoryName(executablePath)!,
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true
        };
        startInfo.ArgumentList.Add(fullCsvPath);

        using var process = new Process { StartInfo = startInfo };
        if (!process.Start()) throw new InvalidOperationException("tower_floorplate_generator.exe did not start.");

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
            try { process.Kill(entireProcessTree: true); } catch { /* The process may already have exited. */ }
            throw new TimeoutException("tower_floorplate_generator.exe exceeded its 5-minute run limit.");
        }

        var output = await stdoutTask;
        var errors = await stderrTask;
        if (process.ExitCode != 0)
            throw new InvalidOperationException(string.IsNullOrWhiteSpace(errors)
                ? $"tower_floorplate_generator.exe exited with code {process.ExitCode}. {output.Trim()}".Trim()
                : $"tower_floorplate_generator.exe failed: {errors.Trim()}");

        var resultLine = output.Split(new[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries)
            .Select(line => line.Trim())
            .LastOrDefault(line => !string.IsNullOrWhiteSpace(line));
        if (string.IsNullOrWhiteSpace(resultLine))
            throw new InvalidDataException("tower_floorplate_generator.exe completed without printing the saved JSON path.");

        foreach (var prefix in new[] { "OUTPUT_PATH=", "OUTPUT_DIR=", "JSON_PATH=", "Output file:", "Output folder:", "Saved JSON:", "Saved folder:" })
            if (resultLine.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
            {
                resultLine = resultLine[prefix.Length..].Trim();
                break;
            }
        resultLine = resultLine.Trim('"');

        var candidates = Path.IsPathRooted(resultLine)
            ? new[] { Path.GetFullPath(resultLine) }
            : new[]
            {
                Path.GetFullPath(resultLine, Path.GetDirectoryName(executablePath)!),
                Path.GetFullPath(resultLine, Path.GetDirectoryName(fullCsvPath)!),
                Path.GetFullPath(resultLine, Environment.CurrentDirectory)
            };
        var outputPath = candidates.FirstOrDefault(candidate => File.Exists(candidate) || Directory.Exists(candidate));
        return outputPath ?? throw new FileNotFoundException(
            $"tower_floorplate_generator.exe reported '{resultLine}', but that file or folder could not be found.");
    }
}
