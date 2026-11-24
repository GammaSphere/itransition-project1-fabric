[StagingDefinition = [Kind = "FastCopy"]]
section Section1;
[DataDestinations = {[Definition = [Kind = "Reference", QueryName = "weather_hourly_raw_DataDestination", IsNewTarget = true], Settings = [Kind = "Automatic", TypeSettings = [Kind = "Table"]]]}]
shared weather_hourly_raw = let
    // Open-Meteo historical weather for New York City, hourly, in UTC. The archive is about
    // five days behind, so the request ends six days ago. The response holds one array per variable.
    EndDate = Date.ToText(Date.AddDays(Date.From(DateTimeZone.UtcNow()), -6), "yyyy-MM-dd"),
    Source = Json.Document(Web.Contents("https://archive-api.open-meteo.com/v1/archive", [Query = [
        latitude = "40.7128",
        longitude = "-74.0060",
        start_date = "2024-01-01",
        end_date = EndDate,
        hourly = "temperature_2m,precipitation,wind_speed_10m,relative_humidity_2m",
        timezone = "GMT"
    ]])),
    Hourly = Source[hourly],
    Result = Table.FromColumns(
        {Hourly[time], Hourly[temperature_2m], Hourly[precipitation], Hourly[wind_speed_10m], Hourly[relative_humidity_2m]},
        type table [ts = text, temperature_c = number, precipitation_mm = number, wind_speed_kmh = number, relative_humidity_pct = number])
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
