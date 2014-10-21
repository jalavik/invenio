/*
 * This file is part of Invenio.
 * Copyright (C) 2013, 2014 CERN.
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


define(function(require, exports, module) {
  'use strict';

  var $ = require('jquery'),
  defineComponent = require('flight/component')

  return defineComponent(actionWidget);

  function actionWidget() {
    this.defaultAttrs({
      // URLs
      action_url: "",

      // Selectors
      actionSelector: ".approval-action",
    });


    this.get_action_values = function (elem) {
      return {
        "value": elem.getAttribute("data-value"),
        "objectid": elem.getAttribute("data-objectid"),
      }
    };

    this.post_request = function(data) {
      console.log(data.message);
    };

    this.onActionClick = function (event) {
      var data = this.get_action_values(event.currentTarget);
      jQuery.ajax({
        type: "POST",
        url: this.attr.action_url,
        data: {
          "objectid": data.objectid,
          "value": data.value
        },
        success: function(data) {
          post_request(data);
        }
      });
    };

    this.after('initialize', function() {
      // Custom handlers
      this.on(this.attr.actionSelector,
              "click",
              this.onActionClick);
    });
  }
});
