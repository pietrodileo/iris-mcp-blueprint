/// Business Process that exposes two HTTP services on top of the
/// <class>MCPTest.Employer</class> / <class>MCPTest.Employee</class> tables:
/// <ol>
/// <li><b>employers</b> - return all the companies (employers).</li>
/// <li><b>employees</b> - return all the employees related to a specific company.</li>
/// </ol>
/// 
/// The service to invoke is selected via the <b>service</b> HTTP header
/// (allowed values: <i>employers</i>, <i>employees</i>; <i>employee</i> is accepted as an alias for <i>employees</i>). For the
/// <i>employees</i> service the company is identified by the <b>employer-id</b>
/// HTTP header (the Employer ID).
Class MCPTest.BP.QueryService Extends MCPTest.BP.Abstract
{

Parameter SERVICEEMPLOYERS As STRING = "employers";

Parameter SERVICEEMPLOYEES As STRING = "employees";

/// Entry point. Dispatches to the requested service based on the
/// <b>service</b> HTTP header and returns a JSON HTTP response.
Method OnRequest(pRequest As EnsLib.HTTP.GenericMessage, Output pResponse As EnsLib.HTTP.GenericMessage) As %Status
{
    Set sc = $$$OK
    Try {
        Set service = $ZCONVERT(pRequest.HTTPHeaders.GetAt("service"), "L")
        $$$LOGINFO("QueryService request - service: '"_service_"'")

        If service = ..#SERVICEEMPLOYERS {
            Set sc = ..GetAllEmployers(.pResponse)
            $$$ThrowOnError(sc)
        } ElseIf service = ..#SERVICEEMPLOYEES {
            Set employerId = pRequest.HTTPHeaders.GetAt("employer-id")
            If employerId = "" {
                Set sc = ..GenerateErrorResponse("Missing required HTTP header 'employer-id'", 400, .pResponse)
                $$$ThrowOnError(sc)
                Quit
            }
            Set sc = ..GetEmployeesByEmployer(employerId, .pResponse)
            $$$ThrowOnError(sc)
        } Else {
            Set msg = "Unknown or missing 'service' HTTP header. Expected '"_..#SERVICEEMPLOYERS_"', '"_..#SERVICEEMPLOYEES_"', or 'employee' (alias for employees)."
            Set sc = ..GenerateErrorResponse(msg, 400, .pResponse)
            $$$ThrowOnError(sc)
        }
    } Catch ex {
        $$$LOGERROR("QueryService failure: "_ex.DisplayString())
        Set sc = ..GenerateErrorResponse(ex.DisplayString(), 500, .pResponse)
        If $$$ISERR(sc) Set sc = ex.AsStatus()
    }
    Return sc
}

/// Service 1 - Build a JSON array with every employer in the database.
Method GetAllEmployers(Output pResponse As EnsLib.HTTP.GenericMessage) As %Status
{
    Set sc = $$$OK
    Try {
        Set list = []
        Set sql = "SELECT ID, Name, Country, FoundedYear FROM MCPTest.Employer ORDER BY Name"
        Set stmt = ##class(%SQL.Statement).%New()
        Set sc = stmt.%Prepare(sql)
        Set rs = stmt.%Execute()
        While rs.%Next() {
            Do list.%Push({
                "id": (rs.%Get("ID")),
                "name": (rs.%Get("Name")),
                "country": (rs.%Get("Country")),
                "foundedYear": (rs.%Get("FoundedYear"))
            })
        }
        Set body = {
            "count": (list.%Size()),
            "employers": (list)
        }
        Set sc = ..GenerateResponse(body, 200, .pResponse)
        $$$ThrowOnError(sc)
    } Catch ex {
        Set sc = ex.AsStatus()
    }
    Return sc
}

/// Service 2 - Build a JSON object describing the employer identified by
/// <var>employerId</var> and the list of its employees. Returns HTTP 404
/// when the employer does not exist.
Method GetEmployeesByEmployer(employerId As %String, Output pResponse As EnsLib.HTTP.GenericMessage) As %Status
{
    Set sc = $$$OK
    Try {
        Set employer = ##class(MCPTest.Employer).%OpenId(employerId, , .openSC)
        If '$ISOBJECT(employer) {
            Set sc = ..GenerateErrorResponse("Employer with id '"_employerId_"' not found", 404, .pResponse)
            $$$ThrowOnError(sc)
            Quit
        }

        Set employees = []
        Set key = ""
        For {
            Set emp = employer.Employees.GetNext(.key)
            Quit:'$ISOBJECT(emp)
            Do employees.%Push({
                "ssn": (emp.SSN),
                "name": (emp.Name),
                "country": (emp.Country),
                "monthlySalary": (emp.MonthlySalary)
            })
        }

        Set body = {
            "employer": {
                "id": (employer.%Id()),
                "name": (employer.Name),
                "country": (employer.Country),
                "foundedYear": (employer.FoundedYear)
            },
            "count": (employees.%Size()),
            "employees": (employees)
        }
        Set sc = ..GenerateResponse(body, 200, .pResponse)
        $$$ThrowOnError(sc)
    } Catch ex {
        Set sc = ex.AsStatus()
    }
    Return sc
}

Storage Default
{
<Type>%Storage.Persistent</Type>
}

}
