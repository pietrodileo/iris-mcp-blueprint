/// To generate data for the employer class, run the following command:
/// do ##class(MCPTest.Employer).%Populate(5)
Class MCPTest.Employer Extends (%Persistent, %Populate)
{

/// Name of the employer.
Property Name As %String(MAXLEN = 200) [ Required ];

/// Country code or country name where the employer is based.
Property Country As %String(MAXLEN = 100);

/// Year the company was founded.
Property FoundedYear As %Integer(MAXVAL = 2100, MINVAL = 1800);

/// One employer has many employees.
Relationship Employees As MCPTest.Employee [ Cardinality = many, Inverse = Employer ];

Index NameIdx On Name;

/// Total monthly payroll cost for this employer (sum of all employees' monthly salary).
ClassMethod GetMonthlyCost(employerName As %String) As %Numeric
{
    Set employer = ##class(MCPTest.Employer).NameIdxOpen(employerName, , .openSC)
    Quit:'$ISOBJECT(employer) $$$ERROR($$$GeneralError, "Employer not found")
    Return employer.GetMonthlyCost()
}

/// Associate an existing <class>MCPTest.Employee</class> (located by SSN)
/// with this employer. Returns the linked Employee object, or "" if no
/// employee with that SSN exists.
Method AddEmployee(ssn As %String) As MCPTest.Employee
{
    Set emp = ##class(MCPTest.Employee).SSNIdxOpen(ssn)
    Quit:'$ISOBJECT(emp) ""
    Set emp.Employer = $THIS
    Do emp.%Save()
    Return emp
}

/// Utility: populate the Employee table first (no Employer link yet),
/// then populate the Employer table, then walk through every Employee and
/// associate it with a randomly chosen Employer via <method>AddEmployee</method>.
/// Returns a one-line summary suitable for run_class_method.
ClassMethod PopulateAndAssign(employeeCount As %Integer = 100, employerCount As %Integer = 5) As %Status
{
    Set sc = $$$OK
    Try {
        Set createdEmployees = ##class(MCPTest.Employee).Populate(employeeCount)
        Set createdEmployers = ..Populate(employerCount)

        Set employerIds = ""
        Set sql = "SELECT ID FROM MCPTest.Employer ORDER BY ID"
        Set stmt = ##class(%SQL.Statement).%New()
        Set sc = stmt.%Prepare(sql)
        Set rs = stmt.%Execute()
        While rs.%Next() {
            Set $LIST(employerIds,*+1) = rs.%Get("ID")
        }
        Set employerCnt = $LISTLENGTH(employerIds)
        If employerCnt = 0 Return "ERROR: no employers were created"
        w "Employer count: ", employerCnt, !
        
        Set assigned = 0, missing = 0
        w "Assigning employees to employers...", !
        k rs, stmt, sql
        Set sql = "SELECT SSN FROM MCPTest.Employee ORDER BY SSN"
        Set stmt = ##class(%SQL.Statement).%New()
        Set sc = stmt.%Prepare(sql)
        Set rs = stmt.%Execute()
        While rs.%Next() {
            Set ssn = rs.%Get("SSN")
            Set employerId = $LISTGET(employerIds, $RANDOM(employerCnt) + 1)
            w "Assigning employee ", ssn, " to employer ", employerId, !
            Set employer = ##class(MCPTest.Employer).%OpenId(employerId)
            Continue:'$ISOBJECT(employer)
            Set emp = employer.AddEmployee(ssn)
            If $ISOBJECT(emp) {
                Set assigned = assigned + 1
                w "Employee ", ssn, " assigned to employer ", employerId, " (", emp.%Id(), ")", !
            } Else {
                Set missing = missing + 1
                w "Employee ", ssn, " not assigned to employer ", employerId, " (", employer.%Id(), ")", !
            }
        }
        w "Created ", createdEmployees, " employees, ", createdEmployers, " employers, assigned ", assigned, " (missing ", missing, ").", !
        k rs, stmt, sql, employerIds, createdEmployees, createdEmployers, employerCnt, assigned, missing
    } Catch ex {
        Set sc = ex.AsStatus()
        w "ERROR: ", ex.DisplayString(), !
    }
    Return sc
}

Storage Default
{
<Data name="EmployerDefaultData">
<Value name="1">
<Value>%%CLASSNAME</Value>
</Value>
<Value name="2">
<Value>Name</Value>
</Value>
<Value name="3">
<Value>Country</Value>
</Value>
<Value name="4">
<Value>FoundedYear</Value>
</Value>
</Data>
<DataLocation>^MCPTest.EmployerD</DataLocation>
<DefaultData>EmployerDefaultData</DefaultData>
<IdLocation>^MCPTest.EmployerD</IdLocation>
<IndexLocation>^MCPTest.EmployerI</IndexLocation>
<StreamLocation>^MCPTest.EmployerS</StreamLocation>
<Type>%Storage.Persistent</Type>
}

}
