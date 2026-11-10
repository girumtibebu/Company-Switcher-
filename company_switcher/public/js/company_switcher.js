// Company switcher at the top left of Desk.
//
// Tick the companies to work in: lists, link searches and list-based reports show only
// their records. Users with access to a single company see it, but cannot switch.
// The choice is saved on the server (company_switcher.company_scope).
(function () {
	const METHOD = "company_switcher.company_scope.";
	let state = null;
	let $pill = null;
	let $panel = null;

	const leaves = () => state.companies.filter((c) => !c.is_group);
	const children = (name) => state.companies.filter((c) => c.parent === name);
	function leaves_under(name) {
		return children(name).flatMap((c) => (c.is_group ? leaves_under(c.name) : [c.name]));
	}

	// "All companies", a group's name when exactly its companies are picked, one name, or abbreviations.
	function label(scope) {
		const all = leaves();
		if (all.length === 1) return all[0].name;
		if (!scope.length || scope.length === all.length) return __("All companies");
		const picked = new Set(scope);
		const group = state.companies.find((c) => {
			if (!c.is_group) return false;
			const under = leaves_under(c.name);
			return under.length === picked.size && under.every((n) => picked.has(n));
		});
		if (group) return group.name;
		if (scope.length === 1) return scope[0];
		const abbr = Object.fromEntries(all.map((c) => [c.name, c.abbr || c.name]));
		return scope.map((name) => abbr[name]).join(" + ");
	}

	function render_pill() {
		if (!leaves().length) return;
		const single = leaves().length === 1;
		const text = label(state.scope || []);
		const html = `
			<button type="button" class="company-switcher btn-reset ${single ? "is-single" : ""}"
				title="${frappe.utils.escape_html(single ? text : __("Switch company"))}">
				<span class="company-switcher-icon">${frappe.utils.icon("building", "sm")}</span>
				<span class="company-switcher-label">${frappe.utils.escape_html(text)}</span>
				${single ? "" : `<span class="company-switcher-caret">${frappe.utils.icon("chevron-down", "xs")}</span>`}
			</button>`;
		if ($pill) $pill.remove();
		$pill = $(html);
		if (!single) $pill.on("click", (e) => (e.preventDefault(), e.stopPropagation(), toggle_panel()));
		mount();
	}

	// Top left of the screen: under the sidebar header on the v16 desk, in the navbar on older layouts.
	function mount() {
		if (!$pill || document.body.contains($pill[0])) return;
		const $sidebar_header = $(".body-sidebar .sidebar-header").first();
		const $brand = $(".navbar .navbar-brand, .navbar .navbar-home").first();
		if ($sidebar_header.length) {
			$pill.addClass("in-sidebar").insertAfter($sidebar_header);
		} else if ($brand.length) {
			$pill.addClass("in-navbar").insertAfter($brand);
		} else {
			$pill.addClass("is-floating").appendTo(document.body);
		}
	}

	function toggle_panel() {
		if ($panel) return close_panel();
		const chosen = new Set(state.scope || []);
		const rows = state.companies
			.map((c) => {
				const pad = 6 + c.depth * 18;
				const checked = c.is_group ? leaves_under(c.name).every((n) => chosen.has(n)) : chosen.has(c.name);
				return `
				<label class="company-switcher-row ${c.is_group ? "is-group" : ""}" style="padding-left:${pad}px">
					<input type="checkbox" data-company="${frappe.utils.escape_html(c.name)}"
						data-group="${c.is_group ? 1 : 0}" ${checked ? "checked" : ""}>
					<span class="company-switcher-abbr">${frappe.utils.escape_html(c.abbr || "")}</span>
					<span>${frappe.utils.escape_html(c.name)}</span>
				</label>`;
			})
			.join("");
		$panel = $(`
			<div class="company-switcher-panel" role="dialog" aria-label="${__("Companies")}">
				<div class="company-switcher-title">${__("Show data from")}</div>
				<div class="company-switcher-list">${rows}</div>
				<div class="company-switcher-actions">
					<button type="button" class="btn btn-xs btn-default" data-action="all">${__("All")}</button>
					<button type="button" class="btn btn-xs btn-primary" data-action="apply">${__("Apply")}</button>
				</div>
			</div>`).appendTo(document.body);
		const rect = $pill[0].getBoundingClientRect();
		$panel.css({ top: rect.bottom + 6, left: Math.max(8, rect.left) });
		$panel.on("click", (e) => e.stopPropagation());
		$panel.on("change", "input", (e) => {
			const $box = $(e.currentTarget);
			if ($box.data("group")) {
				// a group ticks or unticks everything under it
				const under = new Set(leaves_under($box.data("company")));
				$panel.find("input").each((_, el) => {
					if (under.has(el.dataset.company)) el.checked = $box.prop("checked");
				});
			}
			sync_groups();
		});
		$panel.find('[data-action="all"]').on("click", () => $panel.find("input").prop("checked", true));
		$panel.find('[data-action="apply"]').on("click", apply);
		sync_groups();
		setTimeout(() => $(document).one("click", close_panel));
	}

	// A group box is ticked when all its companies are, half-ticked when some are.
	function sync_groups() {
		const ticked = new Set(
			$panel.find('input[data-group="0"]:checked').map((_, el) => el.dataset.company).get()
		);
		$panel.find('input[data-group="1"]').each((_, el) => {
			const under = leaves_under(el.dataset.company);
			const count = under.filter((n) => ticked.has(n)).length;
			el.checked = under.length > 0 && count === under.length;
			el.indeterminate = count > 0 && count < under.length;
		});
	}

	function close_panel() {
		if ($panel) $panel.remove();
		$panel = null;
	}

	function apply() {
		const companies = $panel.find('input[data-group="0"]:checked').map((_, el) => el.dataset.company).get();
		if (!companies.length) {
			frappe.show_alert({ message: __("Pick at least one company"), indicator: "orange" });
			return;
		}
		frappe.call(METHOD + "set_scope", { companies }).then(() => {
			close_panel();
			// lists, sidebars and defaults are all cached on the page; start fresh
			window.location.reload();
		});
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
		if (state || frappe.session.user === "Guest") return;
		state = frappe.boot.company_switcher || null;
		if (!state) return;
		render_pill();
		// the sidebar is rebuilt on some route changes; put the switcher back when that happens
		frappe.router?.on?.("change", () => setTimeout(mount, 50));
		new MutationObserver(() => mount()).observe(document.body, { childList: true, subtree: false });
	});
})();
