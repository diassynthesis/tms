# -*- encoding: utf-8 -*-
##############################################################################
#    
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 HESATEC (<http://www.hesatecnica.com>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.     
#
##############################################################################

{   
    "name" : "Transportation Management System",
    "version" : "1.0",
    "category" : "Transportation Management System",
    'complexity': "normal",
    "author" : "HESATEC",
    "website": "http://www.hesatecnica.com",
    "depends" : ["hr", "account", "account_voucher", "sale"],
    "description": "Transportation Management System",
    "demo_xml" : [],
    "init_xml" : [],
    "update_xml" : [
#                    'security/ir.model.access.csv',
                    'product_view.xml',
                    'ir_sequence_view.xml',
                    'account_view.xml',
                    'hr_view.xml',
                    'partner_view.xml',
                    'sale_view.xml',
                    'tms_view.xml',
                    'tms_travel_view.xml',
                    'tms_advance_view.xml',
                    'tms_fuelvoucher_view.xml',
                    'tms_waybill_view.xml',
                    'tms_expense_view.xml',
                    'tms_factor_view.xml',
                    'tms_history_view.xml',
                    ],
    "active": False,
    'application': True,
    "installable": True
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

