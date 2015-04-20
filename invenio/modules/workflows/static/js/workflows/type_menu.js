/*
 * This file is part of Invenio.
 * Copyright (C) 2014, 2015 CERN.
 *
 * Invenio is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License as
 * published by the Free Software Foundation; either version 2 of the
 * License, or (at your option) any later version.
 *
 * Invenio is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with Invenio; if not, write to the Free Software Foundation, Inc.,
 * 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
 */


define(
  [
    'jquery',
    'flight/lib/component'
  ],
  function(
    $,
    defineComponent) {

    'use strict';

    return defineComponent(HoldingPenTypeMenu);

    /**
    * .. js:class:: HoldingPenTypeMenu()
    *
    * Holding Pen type dropdown.
    *
    *
    */
    function HoldingPenTypeMenu() {
      this.attributes({
        typeMenuitemSelector: "#type-menu a"
      });

      this.addTypeFromMenu = function(ev, data) {
        var value = "type:" + data.el.name;
        this.trigger(document, "addTagFromMenu", {
          value: value,
          text: value,
        });
      };

      this.after('initialize', function() {
        this.on("click", {
          typeMenuitemSelector: this.addTypeFromMenu,
        });
        console.log("Type init");
      });
    }
});
