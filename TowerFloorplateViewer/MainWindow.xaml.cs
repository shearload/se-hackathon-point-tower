using System.Globalization;
using System.IO;
using System.Reflection;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Media;
using Microsoft.Win32;
using Microsoft.Web.WebView2.Core;
using TowerFloorplateViewer.Models;
using TowerFloorplateViewer.Services;

namespace TowerFloorplateViewer;

public partial class MainWindow : Window
{
    private readonly FloorplateJsonService _jsonService = new();
    private readonly LoadModuleService _loadModuleService = new();
    private readonly AnalysisModuleService _analysisModuleService = new();
    private readonly AnalysisResultsService _analysisResultsService = new();
    private readonly StartingValuesConversionService _startingValuesConversionService = new();
    private FloorplateDocument? _document;
    private AnalysisResultsPackage? _analysisResults;
    private IReadOnlyList<StoryForceLoad> _storyLoads = Array.Empty<StoryForceLoad>();
    private string _forceUnit = "kip";
    private string? _buildingInputPath;
    private string? _loadInputPath;
    private string? _analysisResultsPath;
    private string? _selectedGeometryId;
    private string? _selectedCaseName;
    private string _displayMode = "default";
    private const double DiaphragmThicknessInches = 8;
    private bool _viewerReady;
    private bool _isPopulatingAnalysisSelectors;

    public MainWindow()
    {
        InitializeComponent();
        ColorMetricComboBox.SelectionChanged += ColorMetric_SelectionChanged;
        UpdateRunAnalysisButton();
        Loaded += InitializeViewerAsync;
    }

    private async void InitializeViewerAsync(object sender, RoutedEventArgs e)
    {
        OverlayTitle.Text = "Preparing 3D viewer";
        OverlayMessage.Text = "Loading the bundled graphics engine…";
        try
        {
            var webRoot = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "TowerFloorplateViewer", "Web");
            Directory.CreateDirectory(webRoot);
            ExtractEmbeddedAsset("index.html", webRoot);
            ExtractEmbeddedAsset("viewer.js", webRoot);
            ExtractEmbeddedAsset("three.module.js", webRoot);
            ExtractEmbeddedAsset("three.core.js", webRoot);
            ExtractEmbeddedAsset("OrbitControls.js", webRoot);
            ExtractEmbeddedAsset("THREE-LICENSE.txt", webRoot);
            ExtractEmbeddedAsset("logo.html", webRoot);
            ExtractEmbeddedAsset("swoop-logo-braced.svg", webRoot);

            var environment = await CoreWebView2Environment.CreateAsync();
            await Viewer.EnsureCoreWebView2Async(environment);
            Viewer.CoreWebView2.Settings.AreDefaultContextMenusEnabled = false;
            Viewer.CoreWebView2.Settings.AreDevToolsEnabled = false;
            Viewer.CoreWebView2.WebMessageReceived += Viewer_WebMessageReceived;
            Viewer.CoreWebView2.NavigationCompleted += (_, args) =>
            {
                if (!args.IsSuccess)
                {
                    var message = $"Could not load the 3D viewer page ({args.WebErrorStatus}).";
                    ShowStatus(message, true);
                    ShowOverlayError("3D viewer page failed to load", message);
                }
            };
            Viewer.CoreWebView2.SetVirtualHostNameToFolderMapping("appassets.local", webRoot, CoreWebView2HostResourceAccessKind.DenyCors);
            Viewer.Source = new Uri("https://appassets.local/index.html");

            try
            {
                await LogoViewer.EnsureCoreWebView2Async(environment);
                LogoViewer.CoreWebView2.Settings.AreDefaultContextMenusEnabled = false;
                LogoViewer.CoreWebView2.Settings.AreDevToolsEnabled = false;
                LogoViewer.CoreWebView2.SetVirtualHostNameToFolderMapping("brandassets.local", webRoot, CoreWebView2HostResourceAccessKind.DenyCors);
                LogoViewer.Source = new Uri("https://brandassets.local/logo.html");
            }
            catch
            {
                LogoViewer.Visibility = Visibility.Collapsed;
            }
        }
        catch (WebView2RuntimeNotFoundException)
        {
            ShowStatus("Microsoft Edge WebView2 Runtime is required. Install the Evergreen Runtime and restart the viewer.", true);
            ShowOverlayError("WebView2 Runtime required", "Install the Microsoft Edge Evergreen Runtime, then restart the viewer.");
        }
        catch (Exception ex)
        {
            ShowStatus($"Could not initialize the 3D viewer: {ex.Message}", true);
            ShowOverlayError("3D viewer could not start", ex.Message);
        }
    }

    private static void ExtractEmbeddedAsset(string fileName, string destination)
    {
        var resourceName = $"TowerFloorplateViewer.Web.{fileName}";
        var targetPath = Path.Combine(destination, fileName);
        using var source = Assembly.GetExecutingAssembly().GetManifestResourceStream(resourceName)
            ?? throw new InvalidOperationException($"Embedded viewer asset is missing: {fileName}");
        using var output = File.Create(targetPath);
        source.CopyTo(output);
    }

    private async void Open_Click(object sender, RoutedEventArgs e)
    {
        var dialog = new OpenFileDialog { Filter = "Tower floorplate JSON (*.json)|*.json|All files (*.*)|*.*", Title = "Open tower floorplate model" };
        if (dialog.ShowDialog(this) != true) return;
        try
        {
            await LoadBuildingAsync(dialog.FileName);
        }
        catch (Exception ex)
        {
            ShowStatus($"Could not load model: {ex.Message}", true);
            MessageBox.Show(this, ex.Message, "Invalid floorplate JSON", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private async void SelectStartingValues_Click(object sender, RoutedEventArgs e)
    {
        var modulePath = FindExternalModule("tower_floorplate_generator.exe");
        if (modulePath is null)
        {
            const string message = "tower_floorplate_generator.exe was not found. Place it in the EXEs folder beside the application or in the workspace EXEs folder.";
            ShowStatus(message, true);
            MessageBox.Show(this, message, "Starting-values converter not found", MessageBoxButton.OK, MessageBoxImage.Warning);
            return;
        }

        var dialog = new OpenFileDialog
        {
            Filter = "Starting values CSV (*.csv)|*.csv|All files (*.*)|*.*",
            Title = "Select starting-values CSV"
        };
        if (dialog.ShowDialog(this) != true) return;

        SelectStartingValuesButton.IsEnabled = false;
        try
        {
            ShowStatus($"Running tower_floorplate_generator.exe on {Path.GetFileName(dialog.FileName)}…");
            var converterOutputPath = await _startingValuesConversionService.ConvertAsync(modulePath, dialog.FileName);
            var buildingJsonPath = converterOutputPath;
            if (Directory.Exists(converterOutputPath))
            {
                var outputDialog = new OpenFileDialog
                {
                    Filter = "Building JSON (*.json)|*.json|All files (*.*)|*.*",
                    InitialDirectory = converterOutputPath,
                    Title = "Select a building JSON from generator output"
                };
                if (outputDialog.ShowDialog(this) != true)
                {
                    ShowStatus("Starting-values conversion completed; no building JSON was selected.");
                    return;
                }
                buildingJsonPath = outputDialog.FileName;
            }

            await LoadBuildingAsync(buildingJsonPath);
            ShowStatus($"Converted starting values and loaded {Path.GetFileName(buildingJsonPath)}.");
        }
        catch (Exception ex)
        {
            ShowStatus($"Starting-values conversion failed: {ex.Message}", true);
            MessageBox.Show(this, ex.Message, "Starting-values conversion failed", MessageBoxButton.OK, MessageBoxImage.Error);
        }
        finally
        {
            SelectStartingValuesButton.IsEnabled = true;
        }
    }

    private async Task LoadBuildingAsync(string path)
    {
        var fullPath = Path.GetFullPath(path);
        var document = await _jsonService.LoadAsync(fullPath);

        _document = document;
        _buildingInputPath = fullPath;
        _loadInputPath = null;
        _analysisResultsPath = null;
        ClearAnalysisResults();
        _storyLoads = Array.Empty<StoryForceLoad>();
        _forceUnit = _document.Units.TryGetValue("force", out var forceUnit) ? forceUnit : "kip";
        _displayMode = "default";
        foreach (var button in DisplayModePanel.Children.OfType<ToggleButton>())
            button.IsChecked = string.Equals(button.Tag?.ToString(), _displayMode, StringComparison.Ordinal);
        DocumentNameText.Text = Path.GetFileName(fullPath);
        LoadInputNameText.Text = "Loads: none";
        AnalysisResultsPathText.Text = "";
        AnalysisResultsPathText.ToolTip = null;
        UpdateRunAnalysisButton();
        if (_viewerReady)
        {
            LoadingOverlay.Visibility = Visibility.Collapsed;
            await SendModelAsync();
        }
        ShowStatus($"Loaded {_document.FloorSequence.Count} floor(s) · {_document.FloorTypes.Count} floor type(s)");
    }

    private async void ImportLoads_Click(object sender, RoutedEventArgs e)
    {
        if (_document is null)
        {
            ShowStatus("Open a tower floorplate model before importing loads.", true);
            return;
        }

        var modulePath = FindLoadModule();
        if (modulePath is null)
        {
            const string message = "LoadImporter.exe was not found. Place it in the EXEs folder beside the application or in the workspace EXEs folder.";
            ShowStatus(message, true);
            MessageBox.Show(this, message, "Load module not found", MessageBoxButton.OK, MessageBoxImage.Warning);
            return;
        }

        var dialog = new OpenFileDialog
        {
            Filter = "Load input JSON (*.json)|*.json|All files (*.*)|*.*",
            Title = "Select load input JSON"
        };
        if (dialog.ShowDialog(this) != true) return;

        _loadInputPath = null;
        _analysisResultsPath = null;
        ClearAnalysisResults();
        _storyLoads = Array.Empty<StoryForceLoad>();
        LoadInputNameText.Text = "Loads: processing…";
        AnalysisResultsPathText.Text = "";
        AnalysisResultsPathText.ToolTip = null;
        UpdateRunAnalysisButton();
        if (_viewerReady) await SendModelAsync();
        ImportLoadsButton.IsEnabled = false;
        try
        {
            ShowStatus($"Running {Path.GetFileName(modulePath)}…");
            var result = await _loadModuleService.RunAsync(modulePath, dialog.FileName, _document);
            _storyLoads = result.Loads;
            _forceUnit = result.ForceUnit;
            _loadInputPath = Path.GetFullPath(dialog.FileName);
            LoadInputNameText.Text = $"Loads: {Path.GetFileName(dialog.FileName)}";
            UpdateRunAnalysisButton();
            if (_viewerReady) await SendModelAsync();
            var status = $"Imported {_storyLoads.Count} story loads · {_forceUnit}";
            if (!string.IsNullOrWhiteSpace(result.Warning)) status += $" · {result.Warning}";
            ShowStatus(status, !string.IsNullOrWhiteSpace(result.Warning));
        }
        catch (Exception ex)
        {
            _loadInputPath = null;
            _storyLoads = Array.Empty<StoryForceLoad>();
            LoadInputNameText.Text = "Loads: not loaded";
            UpdateRunAnalysisButton();
            if (_viewerReady) await SendModelAsync();
            ShowStatus($"Could not import loads: {ex.Message}", true);
            MessageBox.Show(this, ex.Message, "Load import failed", MessageBoxButton.OK, MessageBoxImage.Error);
        }
        finally
        {
            ImportLoadsButton.IsEnabled = true;
        }
    }

    private static string? FindLoadModule()
    {
        return FindExternalModule("LoadImporter.exe");
    }

    private static string? FindAnalysisModule()
    {
        return FindExternalModule("Analysis.exe") ?? FindExternalModule("Analyze.exe");
    }

    private static string? FindExternalModule(string executableName)
    {
        var candidates = new[]
        {
            Path.Combine(AppContext.BaseDirectory, "EXEs", executableName),
            Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "EXEs", executableName)),
            Path.Combine(Environment.CurrentDirectory, "EXEs", executableName)
        };
        return candidates.FirstOrDefault(File.Exists);
    }

    private async void DisplayMode_Click(object sender, RoutedEventArgs e)
    {
        if (sender is not ToggleButton selected || selected.Tag is not string mode) return;
        _displayMode = mode;
        foreach (var button in DisplayModePanel.Children.OfType<ToggleButton>())
            button.IsChecked = ReferenceEquals(button, selected);
        if (_viewerReady) await Viewer.CoreWebView2.ExecuteScriptAsync($"window.floorplateViewer.setDisplayMode('{mode}');");

        if (mode == "loads" && _storyLoads.Count == 0)
            ShowStatus("Load display selected · import a load JSON file to show arrows.");
        else if (mode == "deformed")
            ShowStatus(_analysisResults is null
                ? "Deformed view selected · load analysis results to display displacement."
                : "Deformed view selected · floor motion applied to each story without interpolation (×1000 for visibility).");
        else if (mode == "colors")
        {
            var metric = (ColorMetricComboBox.SelectedItem as ComboBoxItem)?.Content?.ToString();
            ShowStatus(_analysisResults is null
                ? "Color view selected · load analysis results to display result values."
                : metric == "Member DCR"
                    ? "Member DCR is not included in this results file; use displacement or story drift coloring."
                    : $"Color view selected · coloring by {metric}.");
        }
        else
            ShowStatus("Default view · no analysis overlays");
    }

    private async void ColorMetric_SelectionChanged(object sender, System.Windows.Controls.SelectionChangedEventArgs e)
    {
        if (ColorMetricComboBox.SelectedItem is not ComboBoxItem item) return;
        if (_analysisResults is null)
        {
            if (_displayMode == "colors") ShowStatus($"{item.Content} selected · load analysis results to display values.");
            return;
        }
        await SendAnalysisSelectionAsync();
        if (_displayMode == "colors")
            ShowStatus(item.Content?.ToString() == "Member DCR"
                ? "Member DCR is not included in this results file; use displacement or story drift coloring."
                : $"Coloring by {item.Content}.");
    }

    private async void AnalysisSelection_SelectionChanged(object sender, System.Windows.Controls.SelectionChangedEventArgs e)
    {
        if (_isPopulatingAnalysisSelectors || _analysisResults is null) return;
        if (GeometrySelector.SelectedValue is string geometryId) _selectedGeometryId = geometryId;
        if (CaseSelector.SelectedItem is string caseName) _selectedCaseName = caseName;
        await SendAnalysisSelectionAsync();

        if (sender == GeometrySelector && _selectedGeometryId is not null)
            ShowStatus($"Geometry option {_selectedGeometryId} selected · result case {_selectedCaseName}.");
        else if (sender == CaseSelector && _selectedCaseName is not null)
            ShowStatus($"Analysis case {_selectedCaseName} selected · geometry {_selectedGeometryId}.");
    }

    private async void ImportResults_Click(object sender, RoutedEventArgs e)
    {
        if (_document is null)
        {
            ShowStatus("Open the original building JSON before loading analysis results.", true);
            return;
        }

        var dialog = new OpenFileDialog
        {
            Filter = "Analysis results JSON (*.json)|*.json|All files (*.*)|*.*",
            Title = "Select analysis / optimizer results JSON"
        };
        if (dialog.ShowDialog(this) != true) return;
        ImportResultsButton.IsEnabled = false;
        try
        {
            await LoadAnalysisResultsAsync(dialog.FileName);
        }
        catch (Exception ex)
        {
            ClearAnalysisResults();
            _analysisResultsPath = null;
            AnalysisResultsPathText.Text = "";
            if (_viewerReady && _document is not null) await SendModelAsync();
            ShowStatus($"Could not load analysis results: {ex.Message}", true);
            MessageBox.Show(this, ex.Message, "Analysis results could not be loaded", MessageBoxButton.OK, MessageBoxImage.Error);
        }
        finally
        {
            ImportResultsButton.IsEnabled = true;
        }
    }

    private async Task LoadAnalysisResultsAsync(string path)
    {
        if (_document is null) throw new InvalidOperationException("Open the original building JSON first.");
        ShowStatus($"Reading analysis results from {Path.GetFileName(path)}…");
        var results = await _analysisResultsService.LoadAsync(path);
        _analysisResults = results;
        _analysisResultsPath = results.SourcePath;
        _selectedGeometryId = results.GeometryOptions[0].Id;
        _selectedCaseName = results.CaseNames.FirstOrDefault(name => !name.Equals("GRAVITY", StringComparison.OrdinalIgnoreCase))
            ?? results.CaseNames[0];

        _isPopulatingAnalysisSelectors = true;
        try
        {
            CaseSelector.ItemsSource = null;
            CaseSelector.Items.Clear();
            CaseSelector.ItemsSource = results.CaseNames;
            CaseSelector.SelectedItem = _selectedCaseName;
            CaseSelector.IsEnabled = true;

            GeometrySelector.ItemsSource = null;
            GeometrySelector.Items.Clear();
            GeometrySelector.ItemsSource = results.GeometryOptions;
            GeometrySelector.SelectedValue = _selectedGeometryId;
            GeometrySelector.IsEnabled = true;
        }
        finally
        {
            _isPopulatingAnalysisSelectors = false;
        }

        AnalysisResultsPathText.Text = $"Results: {Path.GetFileName(results.SourcePath)}";
        AnalysisResultsPathText.ToolTip = results.SourcePath;
        if (_viewerReady) await SendModelAsync();
        ShowStatus($"Loaded {results.CaseNames.Count} analysis case(s) and {results.GeometryOptions.Count - 1} geometry option(s).");
    }

    private void ClearAnalysisResults()
    {
        _analysisResults = null;
        _selectedGeometryId = null;
        _selectedCaseName = null;
        _isPopulatingAnalysisSelectors = true;
        try
        {
            CaseSelector.ItemsSource = null;
            CaseSelector.Items.Clear();
            CaseSelector.Items.Add(new ComboBoxItem { Content = "Load results to select case" });
            CaseSelector.SelectedIndex = 0;
            CaseSelector.IsEnabled = false;

            GeometrySelector.ItemsSource = null;
            GeometrySelector.Items.Clear();
            GeometrySelector.Items.Add(new ComboBoxItem { Content = "Load results" });
            GeometrySelector.SelectedIndex = 0;
            GeometrySelector.IsEnabled = false;
        }
        finally
        {
            _isPopulatingAnalysisSelectors = false;
        }
    }

    private async Task SendAnalysisSelectionAsync()
    {
        if (!_viewerReady || _analysisResults is null || Viewer.CoreWebView2 is null) return;
        var metric = (ColorMetricComboBox.SelectedItem as ComboBoxItem)?.Content?.ToString() ?? "Element node SRSS sum";
        var geometryJson = JsonSerializer.Serialize(_selectedGeometryId ?? _analysisResults.GeometryOptions[0].Id);
        var caseJson = JsonSerializer.Serialize(_selectedCaseName ?? _analysisResults.CaseNames[0]);
        var metricJson = JsonSerializer.Serialize(metric);
        await Viewer.CoreWebView2.ExecuteScriptAsync($"window.floorplateViewer.setAnalysisSelection({geometryJson}, {caseJson}, {metricJson});");
    }

    private void UpdateRunAnalysisButton()
    {
        RunAnalysisButton.IsEnabled = !string.IsNullOrWhiteSpace(_buildingInputPath)
            && !string.IsNullOrWhiteSpace(_loadInputPath);
    }

    private async void RunAnalysis_Click(object sender, RoutedEventArgs e)
    {
        if (string.IsNullOrWhiteSpace(_buildingInputPath) || string.IsNullOrWhiteSpace(_loadInputPath))
        {
            UpdateRunAnalysisButton();
            return;
        }

        var modulePath = FindAnalysisModule();
        if (modulePath is null)
        {
            const string message = "Analysis.exe was not found. Place it in the EXEs folder beside the application or in the workspace EXEs folder.";
            ShowStatus(message, true);
            MessageBox.Show(this, message, "Analysis module not found", MessageBoxButton.OK, MessageBoxImage.Warning);
            return;
        }

        RunAnalysisButton.IsEnabled = false;
        try
        {
            _analysisResultsPath = null;
            ClearAnalysisResults();
            AnalysisResultsPathText.Text = "Analysis running…";
            AnalysisResultsPathText.ToolTip = null;
            ShowStatus("Running Analysis.exe…");
            var result = await _analysisModuleService.RunAsync(modulePath, _buildingInputPath, _loadInputPath);
            await LoadAnalysisResultsAsync(result.ResultsPath);
            if (!string.IsNullOrWhiteSpace(result.Note)) ShowStatus($"Analysis completed · {result.Note}");
        }
        catch (Exception ex)
        {
            AnalysisResultsPathText.Text = "";
            ShowStatus($"Analysis failed: {ex.Message}", true);
            MessageBox.Show(this, ex.Message, "Analysis failed", MessageBoxButton.OK, MessageBoxImage.Error);
        }
        finally
        {
            UpdateRunAnalysisButton();
        }
    }

    private async void Viewer_WebMessageReceived(object? sender, CoreWebView2WebMessageReceivedEventArgs e)
    {
        var message = e.TryGetWebMessageAsString();
        if (message == "viewer-ready")
        {
            _viewerReady = true;
            if (_document is not null)
            {
                LoadingOverlay.Visibility = Visibility.Collapsed;
                await SendModelAsync();
            }
            else
            {
                OverlayTitle.Text = "Tower Floorplate Viewer";
                OverlayMessage.Text = "Open a JSON model to inspect floor plates, core walls, columns, beams, and diaphragms in 3D.";
            }
        }
        else if (message.StartsWith("viewer-error:", StringComparison.Ordinal))
        {
            var error = message["viewer-error:".Length..];
            ShowStatus($"3D viewer error: {error}", true);
            ShowOverlayError("3D viewer error", error);
        }
    }

    private void ShowOverlayError(string title, string message)
    {
        OverlayTitle.Text = title;
        OverlayMessage.Text = message;
        LoadingOverlay.Visibility = Visibility.Visible;
    }

    private async Task SendModelAsync()
    {
        if (_document is null || Viewer.CoreWebView2 is null) return;
        var payload = JsonSerializer.Serialize(new
        {
            document = _document,
            diaphragmThicknessInches = DiaphragmThicknessInches,
            storyLoads = _storyLoads,
            forceUnit = _forceUnit,
            analysisOptions = _analysisResults?.GeometryOptions,
            selectedGeometryId = _selectedGeometryId,
            selectedCaseName = _selectedCaseName,
            colorMetric = (ColorMetricComboBox.SelectedItem as ComboBoxItem)?.Content?.ToString() ?? "Element node SRSS sum"
        });
        await Viewer.CoreWebView2.ExecuteScriptAsync($"window.floorplateViewer.setModel({payload});");
        await Viewer.CoreWebView2.ExecuteScriptAsync($"window.floorplateViewer.setDisplayMode('{_displayMode}');");
    }

    private void ShowStatus(string message, bool isError = false)
    {
        StatusText.Text = message;
        StatusText.Foreground = isError ? new SolidColorBrush(Color.FromRgb(255, 179, 167)) : Brushes.White;
    }
}
