[StagingDefinition = [Kind = "FastCopy"]]
section Section1;
[DataDestinations = {[Definition = [Kind = "Reference", QueryName = "weather_hourly_raw_DataDestination", IsNewTarget = true], Settings = [Kind = "Automatic", TypeSettings = [Kind = "Table"]]]}]
shared weather_hourly_raw = let
    // Raw Open-Meteo responses landed by the notebook nb_weather_raw, one row per calendar year.
    // Each response holds one array per variable; the arrays are zipped into hourly rows.
    Source = Lakehouse.Contents([HierarchicalNavigation = true, CreateNavigationProperties = false, EnableFolding = false]),
    Navigation_1 = Source{[workspaceId = "079579b3-9bd5-4e12-99c0-82567fe6f719"]}[Data],
    Navigation_2 = Navigation_1{[lakehouseId = "ca3e6a30-6384-41ca-80fd-4a39238c9e5f"]}[Data],
    Navigation_3 = Navigation_2{[Id = "dbo", ItemKind = "Schema"]}[Data],
    Raw = Navigation_3{[Id = "weather_raw_json", ItemKind = "Table"]}[Data],
    Columns = type table [ts = text, temperature_c = number, precipitation_mm = number, wind_speed_kmh = number, relative_humidity_pct = number],
    PerYear = List.Transform(Raw[payload], (payload) =>
        let Hourly = Json.Document(payload)[hourly]
        in Table.FromColumns({Hourly[time], Hourly[temperature_2m], Hourly[precipitation], Hourly[wind_speed_10m], Hourly[relative_humidity_2m]}, Columns)),
    Result = Table.Combine(PerYear, Columns)
in
    Result;
shared weather_hourly_raw_DataDestination = let
  Pattern = Lakehouse.Contents([HierarchicalNavigation = true, EnableVorder = true, OutputMetadataRefresh = true, CreateNavigationProperties = false, EnableFolding = false]),
  Navigation_1 = Pattern{[workspaceId = "079579b3-9bd5-4e12-99c0-82567fe6f719"]}[Data],
  Navigation_2 = Navigation_1{[lakehouseId = "ca3e6a30-6384-41ca-80fd-4a39238c9e5f"]}[Data],
  Navigation_3 = Navigation_2{[Id = "dbo", ItemKind = "Schema"]}[Data],
  TableNavigation = Navigation_3{[Id = "weather_hourly_raw", ItemKind = "Table"]}?[Data]?
in
  TableNavigation;
