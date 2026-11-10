from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from company_switcher import company_scope

USER = "company-scope@example.com"


def ensure_company(name, abbr, parent=None, is_group=0):
	if not frappe.db.exists("Company", name):
		frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": name,
				"abbr": abbr,
				"default_currency": "ETB",
				"country": "Ethiopia",
				"is_group": is_group,
				"parent_company": parent,
			}
		).insert()
	return name


class TestCompanyScope(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.enterContext(patch.object(frappe.db, "commit"))
		self.group = ensure_company("Scope Test Group", "STG", is_group=1)
		self.first = ensure_company("Scope Test One", "STO", parent=self.group)
		self.second = ensure_company("Scope Test Two", "STT", parent=self.group)
		self.outside = ensure_company("Scope Test Outside", "STX")
		if not frappe.db.exists("User", USER):
			frappe.get_doc(
				{"doctype": "User", "email": USER, "first_name": "Scope", "roles": [{"role": "Stock User"}]}
			).insert(ignore_permissions=True)
		frappe.db.delete("User Permission", {"user": USER})
		frappe.defaults.clear_user_default(company_scope.SCOPE_KEY, USER)
		frappe.clear_cache(user=USER)
		self.addCleanup(frappe.set_user, "Administrator")

	def permit(self, company):
		frappe.get_doc(
			{"doctype": "User Permission", "user": USER, "allow": "Company", "for_value": company, "apply_to_all_doctypes": 1}
		).insert(ignore_permissions=True)
		frappe.clear_cache(user=USER)

	def test_user_without_company_permissions_sees_every_company(self):
		allowed = company_scope.get_allowed_companies(USER)
		self.assertIn(self.first, allowed)
		self.assertIn(self.second, allowed)
		self.assertEqual(company_scope.get_scope(USER), allowed)
		self.assertFalse(company_scope.get_permission_query_conditions(USER, "Warehouse"))

	def test_group_companies_hold_no_data_but_show_in_the_tree(self):
		self.assertNotIn(self.group, company_scope.get_allowed_companies(USER))
		frappe.set_user(USER)
		rows = {row["name"]: row for row in company_scope.get_switcher()["companies"]}
		self.assertTrue(rows[self.group]["is_group"])
		self.assertEqual(rows[self.first]["parent"], self.group)
		self.assertEqual(rows[self.first]["depth"], rows[self.group]["depth"] + 1)

	def test_picking_a_group_picks_its_companies(self):
		frappe.set_user(USER)
		company_scope.set_scope([self.group])
		self.assertEqual(set(company_scope.get_scope(USER)), {self.first, self.second})

	def test_permission_on_a_group_covers_its_companies(self):
		self.permit(self.group)
		allowed = set(company_scope.get_allowed_companies(USER))
		self.assertEqual(allowed, {self.first, self.second})

	def test_user_with_one_company_only_gets_that_one(self):
		self.permit(self.first)
		self.assertEqual(company_scope.get_allowed_companies(USER), [self.first])
		frappe.set_user(USER)
		company_scope.set_scope([self.first, self.second])  # the other company is ignored
		self.assertEqual(company_scope.get_scope(USER), [self.first])

	def test_narrowing_the_scope_filters_lists(self):
		frappe.set_user(USER)
		company_scope.set_scope([self.first])
		self.assertEqual(company_scope.get_scope(USER), [self.first])
		condition = company_scope.get_permission_query_conditions(USER, "Warehouse")
		self.assertIn(self.first, condition)
		self.assertNotIn(self.second, condition)
		self.assertEqual(frappe.defaults.get_user_default("Company", USER), self.first)
		names = frappe.get_list("Warehouse", filters={"company": ["in", [self.first, self.second]]}, pluck="company")
		self.assertTrue(names)
		self.assertEqual(set(names), {self.first})

	def test_ticking_every_company_removes_the_filter(self):
		frappe.set_user(USER)
		company_scope.set_scope(company_scope.get_allowed_companies(USER))
		self.assertFalse(company_scope.get_permission_query_conditions(USER, "Warehouse"))

	def test_empty_choice_is_refused(self):
		frappe.set_user(USER)
		with self.assertRaises(frappe.ValidationError):
			company_scope.set_scope([])

	def test_doctypes_without_company_are_left_alone(self):
		frappe.set_user(USER)
		company_scope.set_scope([self.first])
		self.assertFalse(company_scope.get_permission_query_conditions(USER, "Item"))

	def test_company_print_formats_are_in_boot(self):
		from company_switcher.setup import setup_custom_fields

		setup_custom_fields()
		frappe.db.set_value("Company", self.first, "cs_sales_order_print_format", "Standard")
		formats = company_scope.get_company_print_formats()
		self.assertEqual(formats[self.first]["Sales Order"], "Standard")
