Class MCPTest.WebApplications.Manager Extends %RegisteredObject
{

/// Create or update a CSP web application (e.g. /csp/myapp/api) so
/// that an HTTP-based Business Service such as EnsLib.REST.GenericService
/// can be reached from outside.
/// Authentication is set to <i>Unauthenticated</i> for development convenience
ClassMethod RegisterWebApplication(namespace As %String, path As %String, dispatchClass As %String = "EnsLib.REST.GenericService", description As %String = "REST endpoint exposed via the MCP blueprint") As %String
{
    Try {
        New $Namespace
        Set $Namespace = "%SYS"

        Set spec("AutheEnabled") = $$$AutheUnauthenticated
        Set spec("NameSpace") = namespace
        Set spec("Description") = description
        Set spec("IsNameSpaceDefault") = $$$NO
        Set spec("DispatchClass") = dispatchClass
        Set spec("MatchRoles") = ":%All"

        If '##class(Security.Applications).Exists(path) {
            Set sc = ##class(Security.Applications).Create(path, .spec)
            $$$ThrowOnError(sc)
            Return "OK: created web application '"_path_"' (dispatch="_dispatchClass_", namespace="_namespace_")."
        } Else {
            Set sc = ##class(Security.Applications).Modify(path, .spec)
            $$$ThrowOnError(sc)
            Return "OK: updated web application '"_path_"' (dispatch="_dispatchClass_", namespace="_namespace_")."
        }
    } Catch ex {
        Return "ERROR: "_ex.DisplayString()
    }
}

/// Delete a CSP web application by path.
ClassMethod RemoveWebApplication(path As %String) As %String
{
    Try {
        New $Namespace
        Set $Namespace = "%SYS"
        If '##class(Security.Applications).Exists(path) {
            Return "OK: web application '"_path_"' did not exist."
        }
        Set sc = ##class(Security.Applications).Delete(path)
        $$$ThrowOnError(sc)
        Return "OK: deleted web application '"_path_"'."
    } Catch ex {
        Return "ERROR: "_ex.DisplayString()
    }
}

}
