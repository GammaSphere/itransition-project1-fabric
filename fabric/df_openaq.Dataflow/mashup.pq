[StagingDefinition = [Kind = "FastCopy"]]
section Section1;
shared Fld = (rec as any, field as text) as any =>
    // Field of a record that may itself be null (OpenAQ leaves summary/coverage empty on some days).
    if rec = null then null else Record.FieldOrDefault(rec, field, null);
shared RawJson = let
    // Raw OpenAQ API responses landed by the notebook nb_openaq_raw (one row per response page).
    Source = Lakehouse.Contents([HierarchicalNavigation = true, CreateNavigationProperties = false, EnableFolding = false]),
    Navigation_1 = Source{[workspaceId = "079579b3-9bd5-4e12-99c0-82567fe6f719"]}[Data],
    Navigation_2 = Navigation_1{[lakehouseId = "ca3e6a30-6384-41ca-80fd-4a39238c9e5f"]}[Data],
    Navigation_3 = Navigation_2{[Id = "dbo", ItemKind = "Schema"]}[Data],
    Raw = Navigation_3{[Id = "openaq_raw_json", ItemKind = "Table"]}[Data],
    Parsed = Table.AddColumn(Raw, "doc", each Json.Document([payload]))
in
    Parsed;
[DataDestinations = {[Definition = [Kind = "Reference", QueryName = "openaq_locations_raw_DataDestination", IsNewTarget = true], Settings = [Kind = "Automatic", TypeSettings = [Kind = "Table"]]]}]
shared openaq_locations_raw = let
    // One row per sensor of each monitoring location.
    Pages = Table.SelectRows(RawJson, each [kind] = "locations"),
    Locations = List.Combine(List.Transform(Pages[doc], each _[results])),
    Sensors = List.Combine(List.Transform(Locations, (loc) => List.Transform(loc[sensors], (s) => [
        location_id = loc[id],
        location_name = loc[name],
        latitude = Fld(loc[coordinates], "latitude"),
        longitude = Fld(loc[coordinates], "longitude"),
        sensor_id = s[id],
        parameter_name = s[parameter][name],
        units = s[parameter][units]
    ]))),
    Result = Table.FromRecords(Sensors, type table [location_id = Int64.Type, location_name = text, latitude = number, longitude = number, sensor_id = Int64.Type, parameter_name = text, units = text])
in
    Result;
[DataDestinations = {[Definition = [Kind = "Reference", QueryName = "openaq_daily_raw_DataDestination", IsNewTarget = true], Settings = [Kind = "Automatic", TypeSettings = [Kind = "Table"]]]}]
shared openaq_daily_raw = let
    // One row per sensor and day: the daily average with its min, max and number of readings.
    Pages = Table.SelectRows(RawJson, each [kind] = "days"),
    Days = List.Combine(List.Transform(Table.ToRecords(Pages), (p) => List.Transform(p[doc][results], (m) => [
        sensor_id = p[sensor_id],
        day = Text.Start(Fld(Fld(m[period], "datetimeFrom"), "local"), 10),
        value = m[value],
        min_value = Fld(m[summary], "min"),
        max_value = Fld(m[summary], "max"),
        measurements = Fld(m[coverage], "observedCount"),
        parameter_name = m[parameter][name],
        units = m[parameter][units]
    ]))),
    Result = Table.FromRecords(Days, type table [sensor_id = Int64.Type, day = text, value = number, min_value = number, max_value = number, measurements = Int64.Type, parameter_name = text, units = text])
in
    Result;
shared openaq_locations_raw_DataDestination = let
  Pattern = Lakehouse.Contents([HierarchicalNavigation = true, EnableVorder = true, OutputMetadataRefresh = true, CreateNavigationProperties = false, EnableFolding = false]),
  Navigation_1 = Pattern{[workspaceId = "079579b3-9bd5-4e12-99c0-82567fe6f719"]}[Data],
  Navigation_2 = Navigation_1{[lakehouseId = "ca3e6a30-6384-41ca-80fd-4a39238c9e5f"]}[Data],
  Navigation_3 = Navigation_2{[Id = "dbo", ItemKind = "Schema"]}[Data],
  TableNavigation = Navigation_3{[Id = "openaq_locations_raw", ItemKind = "Table"]}?[Data]?
in
  TableNavigation;
shared openaq_daily_raw_DataDestination = let
  Pattern = Lakehouse.Contents([HierarchicalNavigation = true, EnableVorder = true, OutputMetadataRefresh = true, CreateNavigationProperties = false, EnableFolding = false]),
  Navigation_1 = Pattern{[workspaceId = "079579b3-9bd5-4e12-99c0-82567fe6f719"]}[Data],
  Navigation_2 = Navigation_1{[lakehouseId = "ca3e6a30-6384-41ca-80fd-4a39238c9e5f"]}[Data],
  Navigation_3 = Navigation_2{[Id = "dbo", ItemKind = "Schema"]}[Data],
  TableNavigation = Navigation_3{[Id = "openaq_daily_raw", ItemKind = "Table"]}?[Data]?
in
  TableNavigation;
