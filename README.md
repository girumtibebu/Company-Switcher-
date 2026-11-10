# Company Switcher

A company picker for multi-company ERPNext sites, flat or with a group hierarchy.

- **Switcher at the top left of Desk.** Tick the companies to work in. Company-owned lists and link searches (quotations, orders, invoices, stock entries, warehouses, accounts, employees and more) narrow to them. Groups appear as a tree; ticking a group ticks every company under it. Ticking everything shows everything.
- **Respects access.** Users only see companies their Company User Permissions allow (a permission on a group covers the companies under it). A user with a single company sees it and cannot switch. Users with no Company permission see all companies.
- **Default company follows.** The first picked company becomes the user's default company, so new documents start there.
- **Per-company print formats.** Company > Print Formats sets the default print format for Quotation, Sales Order, Sales Invoice, Delivery Note and Purchase Order per company, so each company prints with its own brand.

## Install

```bash
bench get-app https://github.com/girumtibebu/Company-Switcher-
bench --site <site> install-app company_switcher
```

## Adding your own doctypes

Any doctype with a `company` link field can be narrowed by the switcher. In your app's `hooks.py`:

```python
company_switcher_doctypes = ["My Doctype"]

# On Frappe releases without wildcard permission hooks, also add:
permission_query_conditions = {
	"My Doctype": "company_switcher.company_scope.get_permission_query_conditions",
}
```

## Notes

- Records with no company are never hidden.
- Script and query reports aren't filtered; they use the default company, which the switcher sets.
- The scope is saved per user on the server (`company_switcher_scope` user default).

## Tests

```bash
bench --site <site> run-tests --app company_switcher
```
