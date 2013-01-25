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
from tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, float_compare
import decimal_precision as dp
from osv.orm import browse_record, browse_null
import time
from datetime import datetime, date

import openerp




# Travel - Money advance payments for Travel expenses

class tms_advance(osv.osv):
    _name ='tms.advance'
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _description = 'Money advance payments for Travel expenses'

    def _invoiced(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for record in self.browse(cr, uid, ids, context=context):
            invoiced = (record.invoice_id.id)
            paid = (record.invoice_id.state == 'paid') if record.invoice_id.id else False
            res[record.id] =  {'invoiced': invoiced,
                               'invoice_paid': paid
                                }
        return res

    def _amount(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for record in self.browse(cr, uid, ids, context=context):          
            tax_factor = 0.00
            for line in record.product_id.supplier_taxes_id:
                tax_factor = (tax_factor + line.amount) if line.amount <> 0.0 else tax_factor

            subtotal = record.price_unit * record.product_uom_qty
            tax_amount = subtotal * tax_factor
            total = subtotal + tax_amount
            res[record.id] =   {
                            'subtotal'  :   subtotal,
                            'tax_amount':   tax_amount,
                            'total'     :   total,
                    }
        return res


    
    _columns = {
        'name'          : openerp.osv.fields.char('Anticipo', size=64, required=False),
        'state'         : openerp.osv.fields.selection([('draft','Draft'), ('approved','Approved'), ('confirmed','Confirmed'), ('closed','Closed'), ('cancel','Cancelled')], 'State', readonly=True),
        'date'          : openerp.osv.fields.date('Date', states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)],'closed':[('readonly',True)]}, required=True),
        'travel_id'     :openerp.osv.fields.many2one('tms.travel', 'Travel', required=True, states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)],'closed':[('readonly',True)]}),
        'unit_id'       : openerp.osv.fields.related('travel_id', 'unit_id', type='many2one', relation='fleet.vehicle', string='Unit', store=True, readonly=True),                
        'employee_id'   : openerp.osv.fields.related('travel_id', 'employee_id', type='many2one', relation='hr.employee', string='Driver', store=True, readonly=True),                
        'shop_id'       : openerp.osv.fields.related('travel_id', 'shop_id', type='many2one', relation='sale.shop', string='Shop', store=True, readonly=True),
        'product_id'    : openerp.osv.fields.many2one('product.product', 'Product', domain=[('purchase_ok', '=', 1),('tms_category','=','real_expense')],  required=True, states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)],'closed':[('readonly',True)]}),
        'product_uom_qty': openerp.osv.fields.float('Quantity', digits=(16, 4), required=True, states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)],'closed':[('readonly',True)]}),
        'product_uom'   : openerp.osv.fields.many2one('product.uom', 'Unit of Measure ', required=True, states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)],'closed':[('readonly',True)]}),
        'price_unit'    : openerp.osv.fields.float('Price Unit', required=True, digits_compute= dp.get_precision('Sale Price'), states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)],'closed':[('readonly',True)]}),
        'subtotal'      : openerp.osv.fields.function(_amount, method=True, string='Subtotal', type='float', digits_compute= dp.get_precision('Sale Price'), multi=True, store=True),
        'tax_amount'    : openerp.osv.fields.function(_amount, method=True, string='Tax Amount', type='float', digits_compute= dp.get_precision('Sale Price'), multi=True, store=True),
        'total'         : openerp.osv.fields.function(_amount, method=True, string='Total', type='float', digits_compute= dp.get_precision('Sale Price'), multi=True, store=True),

        'notes'         : openerp.osv.fields.text('Notes', states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)],'closed':[('readonly',True)]}),
        
        'create_uid'    : openerp.osv.fields.many2one('res.users', 'Created by', readonly=True),
        'create_date'   : openerp.osv.fields.datetime('Creation Date', readonly=True, select=True),
        'cancelled_by'  : openerp.osv.fields.many2one('res.users', 'Cancelled by', readonly=True),
        'date_cancelled': openerp.osv.fields.datetime('Date Cancelled', readonly=True),
        'approved_by'   : openerp.osv.fields.many2one('res.users', 'Approved by', readonly=True),
        'date_approved' : openerp.osv.fields.datetime('Date Approved', readonly=True),
        'confirmed_by'  : openerp.osv.fields.many2one('res.users', 'Confirmed by', readonly=True),
        'date_confirmed': openerp.osv.fields.datetime('Date Confirmed', readonly=True),
        'closed_by'     : openerp.osv.fields.many2one('res.users', 'Closed by', readonly=True),
        'date_closed'   : openerp.osv.fields.datetime('Date Closed', readonly=True),
        'drafted_by'    : openerp.osv.fields.many2one('res.users', 'Drafted by', readonly=True),
        'date_drafted'  : openerp.osv.fields.datetime('Date Drafted', readonly=True),
        'invoice_id'    : openerp.osv.fields.many2one('account.invoice','Invoice Record', readonly=True),
        'invoiced'      :  openerp.osv.fields.function(_invoiced, method=True, string='Invoiced', type='boolean', multi='invoiced'),               
        'invoice_paid'  :  openerp.osv.fields.function(_invoiced, method=True, string='Paid', type='boolean', multi='invoiced'),
        'currency_id'   : openerp.osv.fields.many2one('res.currency', 'Currency', required=True, states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)],'closed':[('readonly',True)]}),
        'auto_expense'  : openerp.osv.fields.boolean('Auto Expense', help="Check this if you want this product and amount to be automatically created when Travel Expense Record is created."),
        }
    
    _defaults = {
        'date': lambda *a: time.strftime(DEFAULT_SERVER_DATE_FORMAT),
        'state': lambda *a: 'draft',
        'currency_id': lambda self,cr,uid,c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.currency_id.id,
        'product_uom_qty': 1,
        }
    
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Advance number must be unique !'),
        ]
    _order = "name desc, date desc"


    def on_change_amount(self, cr, uid, ids, product_id, product_uom_qty, price_unit):
        res = {'value': {'subtotal': 0.0, 'tax_amount': 0.0, 'total': 0.0, }}
        if not (product_uom_qty and product_id and price_unit):
            return res
        tax_factor = 0.00
        prod_obj = self.pool.get('product.product')
        for line in prod_obj.browse(cr, uid, [product_id], context=None)[0].supplier_taxes_id:
            tax_factor = (tax_factor + line.amount) if line.amount <> 0.0 else tax_factor
        

        subtotal    = price_unit * product_uom_qty
        tax_amount  = subtotal * tax_factor
        total       = subtotal * (1.0 + tax_factor)
        print tax_factor
        print price_unit
        print subtotal
        print tax_amount
        print total

        return {'value': {'subtotal': subtotal, 'total': total, 'tax_amount': tax_amount}}


    def on_change_product_id(self, cr, uid, ids, product_id):
        res = {}
        if not product_id:
            return {}
        prod_obj = self.pool.get('product.product')
        prod = prod_obj.browse(cr, uid, [product_id], context=None)
        return {'value': {'product_uom' : prod[0].uom_id.id}}



    def on_change_travel_id(self, cr, uid, ids, travel_id):
        res = {}
        if not travel_id:
            return {}
        travel_obj = self.pool.get('tms.travel')
        return {'value': {'employee_id' : travel_obj.browse(cr, uid, [travel_id], context=None)[0].employee_id.id,
                          'unit_id' : travel_obj.browse(cr, uid, [travel_id], context=None)[0].unit_id.id,  }               }

                
    def create(self, cr, uid, vals, context=None):
        travel = self.pool.get('tms.travel').browse(cr, uid, vals['travel_id'])
        shop_id = travel.shop_id.id
        shop = self.pool.get('sale.shop').browse(cr, uid, [shop_id])[0]
        seq_id = shop.tms_advance_seq.id
        if shop.tms_advance_seq:
            seq_number = self.pool.get('ir.sequence').get_id(cr, uid, seq_id)
            vals['name'] = seq_number
        else:
            raise osv.except_osv(_('Travel Sequence Error !'), _('You have not defined Advance Sequence for shop ' + shop.name))
        return super(tms_advance, self).create(cr, uid, vals, context=context)


    def action_cancel_draft(self, cr, uid, ids, *args):
        if not len(ids):
            return False
        for advance in self.browse(cr, uid, ids):
            if advance.travel_id.state in ('cancel','closed'):
                raise osv.except_osv(
                        _('Could not set to draft this Advance !'),
                        _('Travel is Closed or Cancelled !!!'))
            else:
                self.write(cr, uid, ids, {'state':'draft','drafted_by':uid,'date_drafted':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        for (id,name) in self.name_get(cr, uid, ids):
            message = _("Advance '%s' has been set to draft state.") % name
            self.log(cr, uid, id, message)
        return True
    
    def action_cancel(self, cr, uid, ids, context=None):
        for advance in self.browse(cr, uid, ids, context=context):
            if advance.invoiced and not advance.invoice_paid:
                wf_service = netsvc.LocalService("workflow")
                wf_service.trg_validate(uid, 'account.invoice', advance.invoice_id.id, 'invoice_cancel', cr)               
                invoice_obj=self.pool.get('account.invoice')
                invoice_obj.write(cr,uid,[advance.invoice_id.id], {'internal_number':False})
                invoice_obj.unlink(cr, uid, [advance.invoice_id.id], context=None)
            elif advance.invoiced and advance.invoice_paid:
                raise osv.except_osv(
                        _('Could not cancel Advance !'),
                        _('This Advance is already paid'))
            elif advance.state in ('draft','approved','confirmed') and advance.travel_id.state in ('closed'):
                raise osv.except_osv(
                        _('Could not cancel Advance !'),
                        _('This Advance is already linked to Travel Expenses record'))
            self.write(cr, uid, ids, {'state':'cancel', 'cancelled_by':uid,'date_cancelled':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
            for (id,name) in self.name_get(cr, uid, ids):
                message = _("Advance '%s' is cancelled.") % name
            self.log(cr, uid, id, message)
        return True

    def action_approve(self, cr, uid, ids, context=None):
        for advance in self.browse(cr, uid, ids, context=context):            
            if advance.state in ('draft'):
                if advance.total <= 0.0:
                     raise osv.except_osv(
                        _('Could not approve Advance !'),
                        _('Total Amount must be greater than zero.'))
                self.write(cr, uid, ids, {'state':'approved', 'approved_by' : uid, 'date_approved':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
                for (id,name) in self.name_get(cr, uid, ids):
                    message = _("Advance '%s' is set to approved.") % name
                self.log(cr, uid, id, message)
        return True

    def action_confirm(self, cr, uid, ids, context=None):
        adv_invoice = self.pool.get('tms.advance.invoice')
        adv_invoice.makeInvoices(cr, uid, ids, context=None)
        for advance in self.browse(cr, uid, ids, context=None):           
            for (id,name) in self.name_get(cr, uid, ids, context=None):
                message = _("Advance '%s' is set to confirmed.") % name
                self.log(cr, uid, id, message)
        return True

    def copy(self, cr, uid, id, default=None, context=None):
        default = default or {}
        default.update({
            'cancelled_by' : False,
            'date_cancelled': False,
            'approved_by' : False,
            'date_approved': False,
            'confirmed_by' : False,
            'date_confirmed': False,
            'closed_by' : False,
            'date_closed': False,
            'drafted_by' : False,
            'date_drafted': False,
            'invoice_id': False,
            'notes': False,
        })
        return super(tms_advance, self).copy(cr, uid, id, default, context)


tms_advance()


# Wizard que permite generar la factura a pagar correspondiente al Anticipo del Operador

class tms_advance_invoice(osv.osv_memory):

    """ To create invoice for each Advance"""

    _name = 'tms.advance.invoice'
    _description = 'Make Invoices from Advances'

    def makeInvoices(self, cr, uid, ids, context=None):

        """
             To get Advance and create Invoice
             @param self: The object pointer.
             @param cr: A database cursor
             @param uid: ID of the user currently logged in
             @param context: A standard dictionary
             @return : retrun view of Invoice
        """

        if context is None:
            record_ids = ids
        else:
            record_ids =  context.get('active_ids',[])

        if record_ids:
            res = False
            invoices = []
            property_obj=self.pool.get('ir.property')
            partner_obj=self.pool.get('res.partner')
            user_obj=self.pool.get('res.users')
            account_fiscal_obj=self.pool.get('account.fiscal.position')
            invoice_line_obj=self.pool.get('account.invoice.line')
            account_jrnl_obj=self.pool.get('account.journal')
            invoice_obj=self.pool.get('account.invoice')
            advance_obj=self.pool.get('tms.advance')
            adv_line_obj=self.pool.get('tms.advance.line')

            journal_id = account_jrnl_obj.search(cr, uid, [('type', '=', 'purchase'),('tms_advance_journal','=', 1)], context=None)
            if not journal_id:
                raise osv.except_osv('Error !',
                                 'You have not defined Advance Purchase Journal...')
            journal_id = journal_id and journal_id[0]

            partner = partner_obj.browse(cr,uid,user_obj.browse(cr,uid,[uid])[0].company_id.partner_id.id)


            cr.execute("select distinct employee_id, currency_id from tms_advance where invoice_id is null and state='approved' and id IN %s",(tuple(record_ids),))
            data_ids = cr.fetchall()
            if not len(data_ids):
                raise osv.except_osv('Aviso !',
                                 'Selected records are not Approved or already sent for payment...')
            print data_ids

            for data in data_ids:

                cr.execute("select id from tms_advance where invoice_id is null and state='approved' and employee_id=" + str(data[0]) + ' and currency_id=' + str(data[1]) + " and id IN %s", (tuple(record_ids),))
                advance_ids = filter(None, map(lambda x:x[0], cr.fetchall()))
                
                inv_lines = []
                notes = "Anticipos de Viaje."
                inv_amount = 0.0
                for line in advance_obj.browse(cr,uid,advance_ids):                    
                    a = line.employee_id.tms_advance_account_id.id
                    if not a:
                        raise osv.except_osv(_('Warning !'),
                                _('There is no advance account defined ' \
                                        'for this driver: "%s" (id:%d)') % \
                                        (line.employee_id.name, line.employee_id.id,))
                    a = account_fiscal_obj.map_account(cr, uid, False, a)


                    inv_line = (0,0, {
                        'name': line.product_id.name + ' - ' + line.travel_id.name + ' - ' + line.name,
                        'origin': line.name,
                        'account_id': a,
                        'price_unit': line.total / line.product_uom_qty,
                        'quantity': line.product_uom_qty,
                        'uos_id': line.product_uom.id,
                        'product_id': line.product_id.id,
#                        'invoice_line_tax_id': [(6, 0, [x.id for x in line.product_id.supplier_taxes_id])],
                        'note': line.notes,
                        'account_analytic_id': False,
                        })
                    inv_lines.append(inv_line)
                    inv_amount += line.total
                
                    notes += '\n' + line.travel_id.name + ' - ' + line.name
                    employee_name = line.employee_id.name + ' (' + str(line.employee_id.id) + ')' # + time.strftime(DEFAULT_SERVER_DATE_FORMAT)
                    advance_name = line.name
                    advance_travel_name = line.travel_id.name
                    advance_prod = line.product_id.name

                a = partner.property_account_payable.id
                if partner and partner.property_payment_term.id:
                    pay_term = partner.property_payment_term.id
                else:
                    pay_term = False

                inv = {
                    'name'              : 'Advance',
                    'origin'            : 'TMS-Advances',
                    'type'              : 'in_invoice',
                    'journal_id'        : journal_id,
                    'reference'         : advance_name + ' -' + employee_name + ' - ' +  advance_prod,
                    'supplier_invoice_number': advance_name + ' -' + employee_name + ' - ' +  advance_prod,
                    'account_id'        : a,
                    'partner_id'        : partner.id,
                    'address_invoice_id': self.pool.get('res.partner').address_get(cr, uid, [partner.id], ['default'])['default'],
                    'address_contact_id': self.pool.get('res.partner').address_get(cr, uid, [partner.id], ['default'])['default'],
                    'invoice_line'      : [x for x in inv_lines],
                    'currency_id'       : data[1],
                    'comment'           : 'TMS-Advance',
                    'payment_term'      : pay_term,
                    'fiscal_position'   : partner.property_account_position.id,
                    'comment'           : notes,
                    'check_total'       : inv_amount,
                }

                inv_id = invoice_obj.create(cr, uid, inv)
                if inv_id:
                    wf_service = netsvc.LocalService("workflow")
                    wf_service.trg_validate(uid, 'account.invoice', inv_id, 'invoice_open', cr)

                invoices.append(inv_id)

                advance_obj.write(cr,uid,advance_ids, {'invoice_id': inv_id, 'state':'confirmed', 'confirmed_by':uid, 'date_confirmed':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})               



        return {
            'domain': "[('id','in', ["+','.join(map(str,invoices))+"])]",
            'name': _('Drivers Advances'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.invoice',
            'view_id': False,
            'context': "{'type':'in_invoice', 'journal_type': 'purchase'}",
            'type': 'ir.actions.act_window'
        }
tms_advance_invoice()



# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

