/// To generate data for the employee class, run the following command:
/// do ##class(MCPTest.Employee).%Populate(100)
/// This will generate 100 employees with random names, countries, and monthly salaries.
Class MCPTest.Employee Extends (%Persistent, %Populate)
{

/// Unique Social Security Number of the employee.
Property SSN As %String(MAXLEN = 100) [ Required ];

Index SSNIdx On SSN [ PrimaryKey, Unique ];

/// Full name of the employee.
Property Name As %String(MAXLEN = 200) [ Required ];

/// Country where the employee works
Property Country As %String(MAXLEN = 100);

/// Gross monthly salary
Property MonthlySalary As %Numeric(MAXVAL = 1000000, MINVAL = 0, SCALE = 2);

/// Many-to-one back-link to the owning employer.
Relationship Employer As MCPTest.Employer [ Cardinality = one, Inverse = Employees ];

Index NameIdx On Name;

Index EmployerIdx On Employer;

Method GetMonthlyCost() As %Numeric
{
    Return ..MonthlySalary
}

Storage Default
{
<Data name="EmployeeDefaultData">
<Value name="1">
<Value>%%CLASSNAME</Value>
</Value>
<Value name="2">
<Value>SSN</Value>
</Value>
<Value name="3">
<Value>Name</Value>
</Value>
<Value name="4">
<Value>Country</Value>
</Value>
<Value name="5">
<Value>MonthlySalary</Value>
</Value>
<Value name="6">
<Value>Employer</Value>
</Value>
</Data>
<DataLocation>^MCPTest.EmployeeD</DataLocation>
<DefaultData>EmployeeDefaultData</DefaultData>
<IdLocation>^MCPTest.EmployeeD</IdLocation>
<IndexLocation>^MCPTest.EmployeeI</IndexLocation>
<StreamLocation>^MCPTest.EmployeeS</StreamLocation>
<Type>%Storage.Persistent</Type>
}

}
