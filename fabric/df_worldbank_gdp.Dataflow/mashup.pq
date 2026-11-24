[DefaultOutputDestinationSettings = [DestinationDefinition = [Kind = "Reference", QueryName = "DefaultDestination", IsNewTarget = true], UpdateMethod = [Kind = "Replace"], DestinationTypeSettings = [Kind = "Table"]], StagingDefinition = [Kind = "FastCopy"]]
section Section1;
[DataDestinations = {[Definition = [Kind = "Reference", QueryName = "worldbank_gdp_raw_DataDestination", IsNewTarget = true], Settings = [Kind = "Automatic", TypeSettings = [Kind = "Table"]]]}]
shared worldbank_gdp_raw = let
    // World Bank indicator NY.GDP.MKTP.CD: GDP in current US dollars, one value per year.
    // The response is a two-element list: paging metadata, then the rows.
    Source = Json.Document(Web.Contents("https://api.worldbank.org/v2/country/USA/indicator/NY.GDP.MKTP.CD?format=json&per_page=1000")),
    Rows = Source{1},
    Records = List.Transform(Rows, each [country_code = _[countryiso3code], year = Int64.From(_[date]), value = _[value]]),
    Result = Table.FromRecords(Records, type table [country_code = text, year = Int64.Type, value = number])
in
    Result;
shared worldbank_gdp_raw_DataDestination = let
  Pattern = Lakehouse.Contents([HierarchicalNavigation = true, EnableVorder = true, OutputMetadataRefresh = true, CreateNavigationProperties = false, EnableFolding = false]),
  Navigation_1 = Pattern{[workspaceId = "079579b3-9bd5-4e12-99c0-82567fe6f719"]}[Data],
  Navigation_2 = Navigation_1{[lakehouseId = "ca3e6a30-6384-41ca-80fd-4a39238c9e5f"]}[Data],
  Navigation_3 = Navigation_2{[Id = "dbo", ItemKind = "Schema"]}[Data],
  TableNavigation = Navigation_3{[Id = "worldbank_gdp_raw", ItemKind = "Table"]}?[Data]?
in
  TableNavigation;
shared DefaultDestination = let
  Source = Lakehouse.Contents([CreateNavigationProperties = false, EnableFolding = false, HierarchicalNavigation = true]),
  Navigation = Source{[workspaceId = "079579b3-9bd5-4e12-99c0-82567fe6f719"]}[Data],
  #"Navigation 1" = Navigation{[lakehouseId = "ca3e6a30-6384-41ca-80fd-4a39238c9e5f"]}[Data],
  #"Navigation 2" = #"Navigation 1"{[Id = "dbo", ItemKind = "Schema"]}[Data]
in
  #"Navigation 2";
