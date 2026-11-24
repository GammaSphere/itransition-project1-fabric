[StagingDefinition = [Kind = "FastCopy"]]
section Section1;
[DataDestinations = {[Definition = [Kind = "Reference", QueryName = "ecb_fx_raw_DataDestination", IsNewTarget = true], Settings = [Kind = "Automatic", TypeSettings = [Kind = "Table"]]]}]
shared ecb_fx_raw = let
    // ECB daily reference rate: US dollars per 1 euro, business days only.
    Source = Csv.Document(Web.Contents("https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?format=csvdata"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Selected = Table.SelectColumns(Promoted, {"TIME_PERIOD", "OBS_VALUE"}),
    Typed = Table.TransformColumnTypes(Selected, {{"TIME_PERIOD", type text}, {"OBS_VALUE", type text}})
in
    Typed;
shared ecb_fx_raw_DataDestination = let
  Pattern = Lakehouse.Contents([HierarchicalNavigation = true, EnableVorder = true, OutputMetadataRefresh = true, CreateNavigationProperties = false, EnableFolding = false]),
  Navigation_1 = Pattern{[workspaceId = "079579b3-9bd5-4e12-99c0-82567fe6f719"]}[Data],
  Navigation_2 = Navigation_1{[lakehouseId = "ca3e6a30-6384-41ca-80fd-4a39238c9e5f"]}[Data],
  Navigation_3 = Navigation_2{[Id = "dbo", ItemKind = "Schema"]}[Data],
  TableNavigation = Navigation_3{[Id = "ecb_fx_raw", ItemKind = "Table"]}?[Data]?
in
  TableNavigation;
