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

(function() {
  define(
    [
      'jquery',
      'flight/component',
    ],
    function($, defineComponent) {
      return defineComponent(HoldingPen);

      function HoldingPen() {
        this.attributes({
          // URLs
          load_url: "",
          context_url: "",
          oSettings: {
            "bFilter": false,
            "bProcessing": true,
            "bServerSide": true,
            "bDestroy": true,
            "aoColumnDefs": [{'bSortable': false, 'aTargets': [1]},
                             {'bSearchable': false, 'bVisible': false, 'aTargets': [0]},
                             {'sWidth': "25%", 'aTargets': [2]},
                             {'sWidth': "25%", 'aTargets': [3]}],
          }
        });

        this.init_datatables = function(ev, data) {
          // DataTables settings
          this.attr.oSettings["sAjaxSource"] = this.attr.load_url;
          this.$node.dataTable(this.attr.oSettings);
        }

        this.reloadTable = function (ev, data) {
          $.ajax({
              type: "POST",
              url: this.attr.load_url,
              data: data,
              contentType: "application/json;charset=UTF-8",
              traditional: true,
              success: function(result) {
                  this.$node.dataTable().fnDraw(false);
              }
          });
    };

        this.after('initialize', function() {
          this.on("initHoldingPenTable", this.init_datatables);
          this.on("reloadHoldingPenTable", this.reloadTable);
          console.log("HP init");
        });
      }
  });
})();
