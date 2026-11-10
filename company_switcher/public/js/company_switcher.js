// Company switcher, as a row in the sidebar header menu (the menu at the top of the sidebar).
//
// The row is titled "Companies" and opens a submenu: "All" at the top picks every company, and the
// companies follow in alphabetical order, each with a toggle. Ticking a group toggles every company
// under it. The choice is saved on the server (company_switcher.company_scope) and the page reloads
// so lists pick it up.
//
// Users with access to a single company don't get the row.
(function () {
	const METHOD = "company_switcher.company_scope.";
	let state = null;

	const leaves = () => state.companies.filter((c) => !c.is_group);
	const leaves_under = (name) => {
		const children = state.companies.filter((c) => c.parent === name);
		return children.flatMap((c) => (c.is_group ? leaves_under(c.name) : [c.name]));
	};

	function save(companies) {
		frappe.call(METHOD + "set_scope", { companies }).then(() => window.location.reload());
	}

	// Ticking a company or group flips its companies; at least one company always stays in use.
	function toggle(company) {
		const under = company.is_group ? leaves_under(company.name) : [company.name];
		const picked = new Set(state.scope || []);
		const all_on = under.every((n) => picked.has(n));
		under.forEach((n) => (all_on ? picked.delete(n) : picked.add(n)));
		if (!picked.size) {
			frappe.show_alert({ message: __("Pick at least one company"), indicator: "orange" });
			return;
		}
		save([...picked]);
	}

	// A check mark in the label marks the companies in use; the menu's own highlight is too faint
	// to read as a tick when everything is picked.
	const CHECKED = "\u2713\u00A0";
	const UNCHECKED = "\u2003";
	const mark = (on) => (on ? CHECKED : UNCHECKED);

	function company_rows() {
		const scope = new Set(state.scope || []);
		const all = leaves().map((c) => c.name);
		const everything = all.length > 0 && all.every((n) => scope.has(n));
		const rows = [
			{
				name: "company-all",
				label: mark(everything) + __("All"),
				icon: "building-2",
				selected: everything,
				onclick: () => save(all),
			},
		];
		const sorted = [...state.companies].sort((a, b) => a.name.localeCompare(b.name));
		for (const company of sorted) {
			const selected = company.is_group
				? leaves_under(company.name).every((n) => scope.has(n))
				: scope.has(company.name);
			rows.push({
				name: `company-${company.name}`,
				label: mark(selected) + company.name,
				icon: company.is_group ? "folder" : "building",
				selected,
				onclick: () => toggle(company),
			});
		}
		return rows;
	}

	// The sidebar header's menu is built fresh on every open, so the row is added there
	// rather than drawn beside the header.
	function install() {
		const Header = window.frappe?.ui?.SidebarHeader;
		if (!Header || Header.prototype.__company_switcher) return;
		const original = Header.prototype.menu_items;
		Header.prototype.menu_items = function () {
			const groups = original.call(this);
			if (!state || leaves().length < 2) return groups;
			const row = {
				name: "company-switcher",
				label: __("Companies"),
				icon: "building",
				submenu: company_rows(),
			};
			// Sits under the Modules / Apps section and above Edit Sidebar.
			const at = Math.min(1, groups.length);
			return [...groups.slice(0, at), { group: "", options: [row] }, ...groups.slice(at)];
		};
		Header.prototype.__company_switcher = true;
	}

	// Each company prints with its own format (Company > Print Formats), not the site-wide default.
	// The form's meta is shared by every open document of that type, so the site default is
	// remembered and put back for companies without their own format.
	const site_default_print_format = {};
	function apply_company_print_format(frm) {
		if (!frm?.meta || !frm.doc) return;
		const formats = frappe.boot.company_print_formats || {};
		if (!(frm.doctype in site_default_print_format)) {
			site_default_print_format[frm.doctype] = frm.meta.default_print_format || null;
		}
		const chosen = frm.doc.company && formats[frm.doc.company]?.[frm.doctype];
		frm.meta.default_print_format = chosen || site_default_print_format[frm.doctype];
	}

	$(document).on("form-refresh", (_e, frm) => apply_company_print_format(frm));

	$(document).on("app_ready startup", () => {
		if (frappe.session.user === "Guest") return;
		state = state || frappe.boot.company_switcher || null;
		install();
	});
})();
