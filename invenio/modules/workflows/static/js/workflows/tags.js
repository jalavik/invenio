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

define(
  [
    'jquery',
    'flight/component',
  ],
  function($, defineComponent) {
    return defineComponent(HoldingPenTags);

    function HoldingPenTags() {
      this.attributes({
        // URLs
        load_url: "",
        context_url: "",
        versionMenuItemSelector: ".version-selection"
      });

      this.init_tags = function() {
        this.$node.tagsinput({
            tagClass: function (item) {
                switch (item) {
                case 'In process':
                    return 'label label-warning';
                case 'Need action':
                    return 'label label-danger';
                case 'Waiting':
                    return 'label label-warning';
                case 'Done':
                    return 'label label-success';
                case 'New':
                    return 'label label-info';
                case 'Error':
                    return 'label label-danger';
                default:
                    return 'badge badge-warning';
                }
            }
        });
      }

      this.addTagFromMenu = function(ev, data) {
        console.log("addTagFromMenu:");
        console.log(data);
        console.log(ev);
        //if ($.inArray(data, tagList) <= -1) {
        //#    $('#tags').tagsinput('add', $(this)[0].text);
        //}
      }

      this.after('initialize', function() {
        this.on("initHoldingPenTable", this.init_tags);
        this.on("click", {
          versionMenuItemSelector: this.addTagFromMenu,
        });
        console.log("Tags init");
      });
    }
});
