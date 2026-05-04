/// Abstract Business Process base class for the MCPTest demo.
/// Provides shared HTTP response helpers used by all concrete BPs.
Class MCPTest.BP.Abstract Extends Ens.BusinessProcess [ Abstract ]
{

Parameter CONTENTTYPEJSON As STRING = "application/json";

Parameter HTTP200OK As STRING = "HTTP/1.1 200 OK";

Parameter HTTP400BADREQUEST As STRING = "HTTP/1.1 400 Bad Request";

Parameter HTTP404NOTFOUND As STRING = "HTTP/1.1 404 Not Found";

Parameter HTTP500INTERNALSERVERERROR As STRING = "HTTP/1.1 500 Internal Server Error";

/// Build an <class>EnsLib.HTTP.GenericMessage</class> response wrapping the given
/// dynamic object as a JSON body, with the appropriate HTTP status headers.
ClassMethod GenerateResponse(OutObj As %DynamicAbstractObject, HTTPStatus As %Integer = 200, Output pResponse As EnsLib.HTTP.GenericMessage) As %Status
{
    Set sc = $$$OK
    Try {
        Set ContentType = ..#CONTENTTYPEJSON
        Set jsonFormatter = ##class(%JSON.Formatter).%New()
        Set pStream = ##class(%Stream.GlobalCharacter).%New()
        Set sc = jsonFormatter.FormatToStream(OutObj, .pStream)
        $$$ThrowOnError(sc)
        Set pResponse = ##class(EnsLib.HTTP.GenericMessage).%New(pStream)
        Set sc = pResponse.HTTPHeaders.SetAt(ContentType, "Content-Type")
        $$$ThrowOnError(sc)
        Set sc = pResponse.HTTPHeaders.SetAt(HTTPStatus, "StatusCode")
        $$$ThrowOnError(sc)
        If HTTPStatus = 500 {
            Set StatusLine = ..#HTTP500INTERNALSERVERERROR
        } ElseIf HTTPStatus = 400 {
            Set StatusLine = ..#HTTP400BADREQUEST
        } ElseIf HTTPStatus = 404 {
            Set StatusLine = ..#HTTP404NOTFOUND
        } Else {
            Set StatusLine = ..#HTTP200OK
        }
        Set sc = pResponse.HTTPHeaders.SetAt(StatusLine, "StatusLine")
        $$$ThrowOnError(sc)
    } Catch ex {
        Set sc = ex.AsStatus()
    }
    Return sc
}

/// Convenience wrapper to build an error response with a JSON body of the form
/// {"error": "<message>"} and the desired HTTP status code.
ClassMethod GenerateErrorResponse(message As %String, HTTPStatus As %Integer = 500, Output pResponse As EnsLib.HTTP.GenericMessage) As %Status
{
    Set err = {"error": (message)}
    Return ..GenerateResponse(err, HTTPStatus, .pResponse)
}

Storage Default
{
<Type>%Storage.Persistent</Type>
}

}
