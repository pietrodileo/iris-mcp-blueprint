/// Minimal Interoperability production with no business hosts yet.
/// Compile this class in IRIS, then call `start_production` with `MCPTest.EmptyProduction`
/// before using `add_production_item` / `create-rest-bp-endpoint` workflows.
Class MCPTest.EmptyProduction Extends Ens.Production
{

XData ProductionDefinition
{
<Production Name="MCPTest.EmptyProduction" LogGeneralTraceEvents="false">
</Production>
}

}
