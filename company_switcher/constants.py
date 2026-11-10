"""Plain constants (no Frappe import, so hooks.py can use them)."""

# Company-owned doctypes the switcher narrows by default. Other apps add their own
# doctypes with a `company_switcher_doctypes` hook (a list of doctype names).
SCOPED_DOCTYPES = (
	# selling
	"Quotation",
	"Sales Order",
	"Sales Invoice",
	"Delivery Note",
	"POS Invoice",
	# buying
	"Material Request",
	"Request for Quotation",
	"Supplier Quotation",
	"Purchase Order",
	"Purchase Receipt",
	"Purchase Invoice",
	# accounts
	"Payment Entry",
	"Payment Request",
	"Journal Entry",
	"Account",
	"Cost Center",
	"Bank Account",
	"Budget",
	# stock
	"Warehouse",
	"Stock Entry",
	"Stock Reconciliation",
	"Pick List",
	"Serial No",
	"Batch",
	# crm / projects
	"Lead",
	"Opportunity",
	"Project",
	"Task",
	"Timesheet",
	"Contract",
	# assets / hr
	"Asset",
	"Employee",
	"Department",
	"Designation",
	"Expense Claim",
	"Employee Advance",
	"Leave Application",
	"Attendance",
	"Salary Slip",
)

PRINT_FORMAT_DOCTYPES = {
	"Quotation": "cs_quotation_print_format",
	"Sales Order": "cs_sales_order_print_format",
	"Sales Invoice": "cs_sales_invoice_print_format",
	"Delivery Note": "cs_delivery_note_print_format",
	"Purchase Order": "cs_purchase_order_print_format",
}
