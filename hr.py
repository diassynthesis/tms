# -*- encoding: utf-8 -*-
##############################################################################
#    
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
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


from osv import osv, fields
import netsvc
import pooler
from tools.translate import _
import decimal_precision as dp
from osv.orm import browse_record, browse_null
import time
from datetime import datetime, date
import openerp

# C el clasificador para Operador / Mecanico del catalogo de empleados
class hr_employee(osv.osv):
    _description ='Employees'
    _name='hr.employee'
    _inherit='hr.employee'
    _columns = {
  	    'tms_category': openerp.osv.fields.selection([('none','N/A'),('driver','Driver'), ('mechanic','Mechanic'),], 'TMS Category', help='Used to define if this person will be used as a Driver (Frieghts related) or Mechanic (Maintenance related)',required=False),
        'tms_advance_account_id': openerp.osv.fields.many2one('account.account', 'Advance Account', domain=[('type', '=', 'other')]), 
        'tms_expense_negative_balance_account_id': openerp.osv.fields.many2one('account.account', 'Negative Balance Account', domain=[('type', '=', 'other')]), 
        'tms_supplier_driver': openerp.osv.fields.boolean('Supplier Driver'), 
        'tms_supplier_id':openerp.osv.fields.many2one('res.partner', 'Supplier', domain=[('supplier', '=', 1)]),
        }

    _defaults = {
        'tms_category': 'none',

    }

hr_employee()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
