/*
 * This file is part of Invenio.
 * Copyright (C) 2013 CERN.
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

var oTable;
var selectedRow;
var rowList = [];
var rowIndexList = [];
var hoveredRow = -1;
var tagList = [];
var recordsToApprove = [];
var defaultcss='#example tbody tr.even:hover, #example tbody tr.odd:hover {background-color: #FFFFCC;}';

url = new Object();

function init_urls(url_) {
    url.load_table = url_.load_table;
    url.batch_widget = url_.batch_widget;
    url.resolve_widget = url_.resolve_widget;
    url.delete_single = url_.delete_single;
    url.refresh = url_.refresh;
    url.widget = url_.widget;
    url.details = url_.details;
}

function init_datatable(version_showing){
    oSettings = {
        "sDom": 'lf<"clear">rtip',
        "bJQueryUI": true,
        "bProcessing": true,
        "bServerSide": true,
        "bDestroy": true,
        "sAjaxSource": url.load_table,
        "oColVis": {
            "buttonText": "Select Columns",
            "bRestore": true,
            "sAlign": "left",
            "iOverlayFade": 1
        },
        "aoColumnDefs":[{'bSortable': false, 'aTargets': [1]},
                        {'bSearchable': false, 'bVisible': false, 'aTargets': [0]},
                        {'sWidth': "25%", 'aTargets': [2]},
                        {'sWidth': "15%", 'aTargets': [4]}],
        "fnRowCallback": function( nRow, aData, iDisplayIndex, iDisplayIndexFull ) {
            var id = aData[0];
            rememberSelected(nRow);
            oSettings = oTable.fnSettings();
            nRow.row_id = id;
            // console.log(nRow.cells[0].firstChild);
            nRow.checkbox = nRow.cells[0].firstChild;
            nRow.addEventListener("click", function(e) {
                selectRow(nRow, e, oSettings);
            });
        },
        "fnDrawCallback": function(){
            $('table#maintable td').bind('mouseenter', function () {
                $(this).parent().children().each(function() {
                    $(this).addClass('maintablerowhover');
                });
            });
            $('table#maintable td').bind('mouseleave', function () {
                $(this).parent().children().each(function() {
                    $(this).removeClass('maintablerowhover');
                });
            });
        }
    };
    oTable = $('#maintable').dataTable(oSettings);
    // $('#tagsinput').tagsinput();
    console.log(version_showing);
    initialize_versions(version_showing);
    // $('#version-halted').click();
    return oTable;
}

// $('#refresh_button').on('click', function() {
//     jQuery.ajax({
//         url: url.refresh,
//         success: function(json){
            
//         }
//     });
//     oTable.fnDraw(false);
// });

// DataTables row selection functions
//***********************************
$("#select-all").on("click", function(){
    selectAll();
})

function hoverRow(row) {
    row.style.background = "#FFFFEE";
}

function unhoverRow(row) {
    console.log(row.row_id);
    if($.inArray(row.row_id, rowList) > -1){
        row.style.background = "#ffa";
    }
    else{
        row.style.cssText = defaultcss;
    }
}

function removeSelection () {
    if (window.getSelection) {  // all browsers, except IE before version 9
        var selection = window.getSelection ();                                        
        selection.removeAllRanges ();
    }
    else {
        if (document.selection.createRange) {        // Internet Explorer
            var range = document.selection.createRange ();
            document.selection.empty ();
        }
    }
}

function selectRange(row){
    var toPos = oTable.fnGetPosition(row) + oSettings._iDisplayStart;
    var fromPos = rowIndexList[rowIndexList.length-1];
    var i;
    var current_row = null;

    if (toPos > fromPos){
        for (i=fromPos; i<=toPos; i++){
            j = i % 10;
            if($.inArray(i, rowIndexList) <= -1){
                current_row = oSettings.aoData[oSettings.aiDisplay[j]].nTr;
                if (selectCellByTitle(current_row, 'Actions').innerText != 'N/A'){
                    rowIndexList.push(i);
                    console.log(current_row.row_id);
                    rowList.push(current_row.row_id);
                    current_row.style.background = "#ffa";
                    // checkbox = selectCellByTitle(oSettings.aoData[oSettings.aiDisplay[j]].nTr, "").childNodes[1];
                    console.log("EDW");
                    current_row.checkbox.checked = true;
                }
            }
        }
    }
    else{
        for (i=fromPos; i>=toPos; i--){
            j = i % 10;
            if($.inArray(i, rowIndexList) <= -1){
                current_row = oSettings.aoData[oSettings.aiDisplay[j]].nTr
                if (selectCellByTitle(current_row, 'Actions').innerText != 'N/A'){
                    rowIndexList.push(i);
                    rowList.push(current_row.row_id);
                    current_row.style.background = "#ffa";
                    current_row.checkbox.checked = false;
                }
            }
        }
    }
    document.getSelection().removeAllRanges();
}

function selectAll(){
    console.log("selecting all");
    var toPos = oSettings._iDisplayEnd - 1;
    var fromPos = 0;

    for (var i=fromPos; i<=toPos; i++){
        if($.inArray(selectCellByTitle(oSettings.aoData[oSettings.aiDisplay[i]].nTr, 'Id').innerText, rowList) <= -1){
            if (selectCellByTitle(oSettings.aoData[oSettings.aiDisplay[i]].nTr, 'Actions').innerText != 'N/A'){
                rowIndexList.push(i);
                rowList.push(selectCellByTitle(oSettings.aoData[oSettings.aiDisplay[i]].nTr, 'Id').innerText);
                oSettings.aoData[oSettings.aiDisplay[i]].nTr.style.background = "#ffa";
            }
        }
    }
}

function rememberSelected(row) {
    selectedRow = row;
    if($.inArray(row.row_id, rowList) > -1){
        selectedRow.style.background = "#ffa";
        //selectedRow.cells[0].childNodes[1].checked = true;
    }
}

window.addEventListener("keydown", function(e){
    var currentRowIndex;
    var current_row;
    if([32, 37, 38, 39, 40].indexOf(e.keyCode) > -1) {
        e.preventDefault();
    }
    if (e.keyCode == 40) {
        if (e.shiftKey === true){
            currentRowIndex = rowIndexList[rowIndexList.length-1];
            if (currentRowIndex < 9){
                row_index = currentRowIndex + 1;
                current_row = oSettings.aoData[oSettings.aiDisplay[row_index]].nTr;
                if($.inArray(current_row.row_id, rowList) <= -1){
                    rowIndexList.push(row_index);
                    rowList.push(current_row.row_id);
                    current_row.style.background = "#ffa";
                }
            }
        }
        else{
            if (hoveredRow < 9){
                if (hoveredRow != -1){
                    unhoverRow(oSettings.aoData[oSettings.aiDisplay[hoveredRow]].nTr);
                }
                hoveredRow++;
                hoverRow(oSettings.aoData[oSettings.aiDisplay[hoveredRow]].nTr);
            }
        }
    }
    else if (e.keyCode == 38) {
        if (e.shiftKey === true){
            currentRowIndex = rowIndexList[rowIndexList.length-1];
            if (currentRowIndex > 0){
                rowToAdd = currentRowIndex - 1;
                if($.inArray(selectCellByTitle(oSettings.aoData[oSettings.aiDisplay[rowToAdd]].nTr, 'Id').innerText, rowList) <= -1){
                    rowIndexList.push(rowToAdd);
                    rowList.push(selectCellByTitle(oSettings.aoData[oSettings.aiDisplay[rowToAdd]].nTr, 'Id').innerText);
                    oSettings.aoData[oSettings.aiDisplay[rowToAdd]].nTr.style.background = "#ffa";
                }
            }
        }
        else{
            if (hoveredRow > 0){
                unhoverRow(oSettings.aoData[oSettings.aiDisplay[hoveredRow]].nTr);
                hoveredRow--;
                hoverRow(oSettings.aoData[oSettings.aiDisplay[hoveredRow]].nTr);
            }
        }
    }
    else if (e.keyCode == 37){
        oTable.fnPageChange('previous');
    }
    else if( e.keyCode == 39){
        oTable.fnPageChange('next');
    }
    else if (e.keyCode == 65 && e.ctrlKey === true){
        selectAll();
        removeSelection();
    }
    else if (e.keyCode == 13 && hoveredRow != -1){
        selectCellByTitle(oSettings.aoData[oSettings.aiDisplay[hoveredRow]].nTr, 'Details').click();
    }
    else if(e.keyCode == 46){
        if (rowList.length >= 1){
            var rowList_out = JSON.stringify(rowList);
            deleteRecords(rowList_out);
            rowList = [];
            rowIndexList = [];
        }
    }
});

function selectCellByTitle(row, title){
    for(var i=0; i<oSettings.aoHeader[0].length; i++){
        var trimmed_title = $.trim(oSettings.aoHeader[0][i].cell.innerText);
        if(trimmed_title === title){
            return $(row).children()[i - 1];
        }
    }
}

function getCellIndex(row, title){
    for(var i=0; i<oSettings.aoHeader[0].length; i++){
        var trimmed_title = $.trim(oSettings.aoHeader[0][i].cell.innerText);
        if(trimmed_title === title){
            return i
        }
    }   
}

function selectRow(row, e, oSettings) {
    console.log(row.row_id);
    selectedRow = row;
    if( e.shiftKey === true ){
        selectRange(row);
    }
    else{
        if(selectCellByTitle(row, 'Actions').childNodes[0].id === 'submitButtonMini'){
            widget_name = 'Approve Record';
        }
        if($.inArray(row.row_id, rowList) <= -1){
            // Select row
            rowList.push(row.row_id);
            rowIndexList.push(row._DT_RowIndex+oSettings._iDisplayStart);
            row.style.background = "#ffa";

            if (selectCellByTitle(row, 'Actions').innerText != 'N/A'){                    
                if(widget_name === 'Approve Record'){
                    recordsToApprove.push(row.row_id);
                    console.log(recordsToApprove);
                }
            }   
            row.checkbox.checked = true;
        }   
        else{
            // De-Select row?? - Yes
            rowList.splice(rowList.indexOf(row.row_id), 1);
            rowIndexList.splice(rowIndexList.indexOf(row._DT_RowIndex+oSettings._iDisplayStart), 1);
            row.style.background = "white";
            
            if(widget_name === 'Approve Record'){
                recordsToApprove.splice(recordsToApprove.indexOf(row.row_id), 1);
            }
            // checkbox = $(selectedRow).find(".hp-check");
            // checkbox.attr('checked', false);
            row.checkbox.checked = false;
        }
    }
    checkRecordsToApprove();
}

function deselectAll(){
    rowList = [];
    rowIndexList = [];
    oTable.fnDraw(false);
    window.getSelection().removeAllRanges();
}

$(document).keyup(function(e){
    if (e.keyCode == 27) {  // esc           
        deselectAll();
    }   
});
//***********************************

// Tags functions
//***********************************
$('.task-btn').on('click', function(){
    if($.inArray($(this)[0].name, tagList) <= -1){
        var widget_name = $(this)[0].name;
        // $('#tag-area').append('<div class="alert alert-info tag-alert col-md-1">'+widget_name+'<a id="'+widget_name+'" class="close-btn pull-right" data-dismiss="alert" name='+widget_name+' onclick="closeTag(this.parentElement)">&times;</a></div>');
        $('#tagsinput').tagsinput('add', $(this)[0].name);
        tagList.push($(this)[0].name);
        // oTable.fnFilter($(this)[0].name);
        requestNewObjects();
    }
    else{
        closeTag(widget_name);
        oTable.fnFilter( '^$', 4, true, false );
        oTable.fnDraw(false);
    }   
});

$('.version-selection').on('click', function(){
    console.log($(this)[0].name);
    console.log(tagList);

    if($.inArray($(this)[0].name, tagList) <= -1){
        console.log("TAG NOT IN TAGLIST");
        // $('#tag-area').append('<div id="tag-version-'+$(this)[0].name+'" name="'+$(this)[0].name+'" class="alert alert-info tag-alert col-md-1">'+$(this)[0].name+'<a class="close-btn pull-right" data-dismiss="alert" onclick="closeTag(this.parentElement)">&times;</a></div>');
        $('#tagsinput').tagsinput('add', $(this)[0].name);
        tagList.push($(this)[0].name);
        requestNewObjects();
    } 
    else{
        console.log("TAG IS IN TAGLIST");
        closeTag($(this)[0].name);
        // $('#tagsinput').tagsinput('remove', $(this)[0].name);
    }    
});

$("#tagsinput").on('itemRemoved', function(event) {
    tagList.splice(tagList.indexOf(event.item), 1);
    console.log('item removed : '+event.item);
    requestNewObjects();
});

$("#tagsinput").on('itemAdded', function(event){
    if(event.item != 'Halted' && event.item != 'Final' && event.item != 'Running'){
        oTable.fnFilter(event.item);
    }
    else if(event.item === 'Halted'){
        $('#version-halted').click();
    }
    else if(event.item === 'Final'){
        $('#version-final').click();   
    }
    else{
        $('version-running').click();
    }
});

function closeTag(tag_name){
//     // console.log(tagList);
//     // console.log(obj.name);
    console.log(tag_name);
    tagList.splice(tagList.indexOf(tag_name), 1);
    $('#tagsinput').tagsinput('remove', tag_name);
    console.log($("#tagsinput").tagsinput('items'));
    requestNewObjects();
};
//***********************************

//Utility functions
//***********************************
function initialize_versions(version_showing){
    if(version_showing){
        for(var i=0; i<version_showing.length; i++){
            if(version_showing[i] == 1){
                if ($.inArray('Final', tagList) <= -1){
                    tagList.push('Final');  
                } 
                $('#version-final').click();
            }
            else if(version_showing[i] == 2){
                if ($.inArray('Halted', tagList) <= -1){
                    tagList.push('Halted');
                } 
                $('#version-halted').click();  
            }
            else if(version_showing[i] == 3){
                if ($.inArray('Halted', tagList) <= -1){
                    tagList.push('Running');
                } 
                $('#version-running').click();  
            }
        }
    }

    if ($.inArray('Final', tagList) > -1) $('#tagsinput').tagsinput('add', 'Final');
    if ($.inArray('Halted', tagList) > -1){
        // $('#tagsinput').tagsinput('add', 'Halted');
        $('#version-halted').click();
        console.log('patisa to halted');
    } 
    if ($.inArray('Running', tagList) > -1) $('#tagsinput').tagsinput('add', 'Running');    
    console.log(tagList);
}

function fnGetSelected( oTableLocal ){
    var aReturn = [];
    var aTrs = oTableLocal.fnGetNodes();
    
    for ( var i=0 ; i<aTrs.length ; i++ ){
        if ($(aTrs[i]).hasClass('row_selected')){
            aReturn.push( aTrs[i] );
        }
    }
    return aReturn;
}

function requestNewObjects(){
    var version_showing = new Object;
    // var widget_showing = new Object;

    version_showing['final'] = ($.inArray('Final', tagList) <= -1) ? false : true;
    version_showing['halted'] = ($.inArray('Halted', tagList) <= -1) ? false : true;
    version_showing['running'] = ($.inArray('Running', tagList) <= -1) ? false : true;

    $.ajax({
        type : "POST",
        url : url.load_table,
        data: JSON.stringify(version_showing),
        contentType: 'application/json;charset=UTF-8',
        traditional: true,
        success: function(result) {
            oTable.fnDraw(false);
        }
    });
}

function isInt(n) {
   return typeof n === 'number' && n % 1 === 0;
}

function emptyLists(){
    rowList = [];
    rowIndexList = [];
}

$.fn.exists = function () {
    return this.length !== 0;
}

function bootstrap_alert(message) {
    $('#alert-message').html('<span class="alert"><a class="close" data-dismiss="alert"> ×</a><span>'+message+'</span></span>');
}
//***********************************


