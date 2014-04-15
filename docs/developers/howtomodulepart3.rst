.. _developers-howtomodulepart3:

How to develop a module: Part 3
===============================

Menu & Breadcrumbs
------------------

To integrate your web interface with menu items and breadcrumbs, you
use the decorators available from :ref:`flask_menu` and :ref:`flask_breadcrumb`

	from flask_breadcrumbs import default_breadcrumb_root, register_breadcrumb
	from flask_menu import register_menu

	default_breadcrumb_root(blueprint, '.yourmodule')

	@register_breadcrumb(blueprint, '.', _('Your Messages'))
	@register_menu(blueprint, 'personalize.messages', _('Your messages')))
	def index():
	    pass




Tests
-----

TODO

Documentation
-------------

TODO