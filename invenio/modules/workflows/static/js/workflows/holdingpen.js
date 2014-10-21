/*
 * This file is part of Invenio.
 * Copyright (C) 2014 CERN.
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

'use strict';

$(function() {
  define(
    [
      'jquery',
      'flight/component',
    ],
    function($, defineComponent) {
      return defineComponent(HoldingPen);

      function HoldingPen() {
        this.defaultAttrs({
          // URLs
          load_url: "",
          context_url: "",

        });

        this.init_datatables = function() {
          // DataTables settings
          var oSettings = {
            "bFilter": false,
            "bProcessing": true,
            "bServerSide": true,
            "bDestroy": true,
            "sAjaxSource": this.attr.load_url,
            "aoColumnDefs": [{'bSortable': false, 'aTargets': [1]},
                             {'bSearchable': false, 'bVisible': false, 'aTargets': [0]},
                             {'sWidth': "25%", 'aTargets': [2]},
                             {'sWidth': "25%", 'aTargets': [3]}],
          };
          this.$node.dataTable(oSettings);
        }

        this.after('initialize', function() {
          this.on("loadHoldingPenTable", this.init_datatables);
        });
      }
  });
});
