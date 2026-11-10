from company_switcher.constants import SCOPED_DOCTYPES

app_name = "company_switcher"
app_title = "Company Switcher"
app_publisher = "emc"
app_description = "Company switcher and per-company print formats for multi-company ERPNext sites"
app_email = "girum@eternal-media.com"
app_license = "mit"

required_apps = ["erpnext"]

app_include_js = "/assets/company_switcher/js/company_switcher.js"
app_include_css = "/assets/company_switcher/css/company_switcher.css"

boot_session = "company_switcher.company_scope.boot_session"

# Narrows company-owned lists to the companies picked in the switcher.
# The default doctypes are listed one by one so it works on every Frappe v16
# release; "*" picks up doctypes other apps add through `company_switcher_doctypes`
# on releases that support wildcard permission hooks.
_condition = "company_switcher.company_scope.get_permission_query_conditions"
permission_query_conditions = {doctype: _condition for doctype in SCOPED_DOCTYPES}
permission_query_conditions["*"] = _condition

after_install = "company_switcher.setup.after_install"
after_migrate = "company_switcher.setup.after_migrate"
