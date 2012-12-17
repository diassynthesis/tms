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
import simplejson as json
import urllib as my_urllib


# Master catalog used for:
# - Unit Types
# - Unit Brands
# - Unit / Motor Models
# - Motor Type
# - Extra Data for Units (Like Insurance Policy, Unit Invoice, etc
# - Unit Status (Still not defined if is keeped or not
# - Documentacion expiraton  for Transportation Units
class fleet_vehicle_category(osv.osv):
    _name = "tms.unit.category"
    _description = "Types, Brands, Models, Motor Type for Transport Units"

    def name_get(self, cr, uid, ids, context=None):
        if not len(ids):
            return []
        reads = self.read(cr, uid, ids, ['name','parent_id'], context=context)
        res = []
        for record in reads:
            name = record['name']
            if record['parent_id']:
                name = record['parent_id'][1]+' / '+name
            res.append((record['id'], name))
        return res

    def _name_get_fnc(self, cr, uid, ids, prop, unknow_none, context=None):
        res = self.name_get(cr, uid, ids, context=context)
        return dict(res)

    _columns = {
        'name': openerp.osv.fields.char('Name', size=30, required=True, translate=True),
        'complete_name': openerp.osv.fields.function(_name_get_fnc, method=True, type="char", size=300, string='Complete Name', store=True),
        'parent_id': openerp.osv.fields.many2one('tms.unit.category','Parent Category', select=True),
        'child_id': openerp.osv.fields.one2many('tms.unit.category', 'parent_id', string='Child Categories'),
        'sequence': openerp.osv.fields.integer('Sequence', help="Gives the sequence order when displaying this list of categories."),
        'type': openerp.osv.fields.selection([
                            ('view','View'), 
                            ('unit_type','Type'), 
                            ('brand','Motor Brand'), 
                            ('motor','Motor'), 
                            ('extra_data', 'Extra Data'),
                            ('unit_status','Unit Status'),
                            ('expiry','Expiry'),
                            ('active_cause','Active / Inactive Causes'),
                            ('red_tape','Red Tape Types'),
                        ], 'Category Type',required=True, help="""Category Types:
 - View: Use this to define tree structure
 - Type: Use this to define Unit types, like Tractor, Trailers, dolly, van, etc.
 - Brand: Units brands
 - Motor: Motors
 - Extra Data: Use to define several extra fields for unit catalog.
 - Expiry: Use it to define several extra fields for units related to document expiration (Ex. Insurance Validity, Plates Renewal, etc)
 - Active / Inactive Causes: Use to define causes for a unit to be Active / Inactive (Ex: Highway Accident, Sold, etc)
 - Red Tape Types: Use it to define all kind of Red Tapes like Unit registration, Traffic Violations, etc.
"""
                ),
        'fuel_efficiency_drive_unit': openerp.osv.fields.float('Fuel Efficiency Drive Unit', required=False, digits=(14,4)),
        'fuel_efficiency_1trailer': openerp.osv.fields.float('Fuel Efficiency One Trailer', required=False, digits=(14,4)),
        'fuel_efficiency_2trailer': openerp.osv.fields.float('Fuel Efficiency Two Trailer', required=False, digits=(14,4)),
        'notes': openerp.osv.fields.text('Notes'),
        'active': openerp.osv.fields.boolean('Active'),
        'mandatory': openerp.osv.fields.boolean('Mandatory', help="This field is used only when field <Category Type> = expiry"),
        'company_id': openerp.osv.fields.many2one('res.company', 'Company', required=False),
    }

    _defaults = {
#        'type' : lambda *a : 'unit_type',
        'active': True,
    }

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Category name number must be unique !'),
        ]


    _order = "sequence"
    
    def _check_recursion(self, cr, uid, ids, context=None):
        level = 100
        while len(ids):
            cr.execute('select distinct parent_id from fleet_vehicle_category where id IN %s',(tuple(ids),))
            ids = filter(None, map(lambda x:x[0], cr.fetchall()))
            if not level:
                return False
            level -= 1
        return True

    _constraints = [
        (_check_recursion, 'Error ! You can not create recursive categories.', ['parent_id'])
    ]

    def child_get(self, cr, uid, ids):
        return [ids]

    def copy(self, cr, uid, id, default=None, context=None):
        categ = self.browse(cr, uid, id, context=context)
        if not default:
            default = {}
        default['name'] = categ['name'] + ' (copy)'
        return super(fleet_vehicle_category, self).copy(cr, uid, id, default, context=context)

fleet_vehicle_category()

                             
# Units for Transportation
class fleet_vehicle(osv.osv):
#    _name = "fleet.vehicle"
    _name = 'fleet.vehicle'
    _inherit = ['fleet.vehicle']
    _description = "All motor/trailer units"

    _columns = {
        'shop_id': openerp.osv.fields.many2one('sale.shop', 'Shop', required=True, readonly=False),
#        'company_id': openerp.osv.fields.related('shop_id','company_id',type='many2one',relation='res.company',string='Company',store=True,readonly=True),
        'name': openerp.osv.fields.char('Unit Name', size=64, required=True),
        'year_model':openerp.osv.fields.char('Year Model', size=64), 
        'unit_type_id':openerp.osv.fields.many2one('tms.unit.category', 'Unit Type', domain="[('type','=','unit_type')]"),
        'unit_brand_id':openerp.osv.fields.many2one('tms.unit.category', 'Brand', domain="[('type','=','brand')]"),
        'unit_model_id':openerp.osv.fields.many2one('tms.unit.category', 'Model', domain="[('type','=','model')]"),
        'unit_motor_id':openerp.osv.fields.many2one('tms.unit.category', 'Motor', domain="[('type','=','motor')]"),
        'serial_number': openerp.osv.fields.char('Serial Number', size=64),
        'vin': openerp.osv.fields.char('VIN', size=64),
        'day_no_circulation': openerp.osv.fields.selection([
                            ('sunday','Sunday'), 
                            ('monday','Monday'), 
                            ('tuesday','Tuesday'), 
                            ('wednesday','Wednesday'), 
                            ('thursday','Thursday'), 
                            ('friday','Friday'), 
                            ('saturday','Saturday'), 
                            ('none','Not Applicable'), 
                           ], string="Day no Circulation", translate=True),
        'registration': openerp.osv.fields.char('Registration', size=64), # Tarjeta de Circulacion
        'gps_supplier_id': openerp.osv.fields.many2one('res.partner', 'GPS Supplier', required=False, readonly=False, 
                                            domain="[('tms_category','=','gps')]"),
        'gps_id': openerp.osv.fields.char('GPS Id', size=64),
        'employee_id': openerp.osv.fields.many2one('hr.employee', 'Driver', required=False, domain=[('tms_category', '=', 'driver')], help="This is used in TMS Module..."),
        'fleet_type': openerp.osv.fields.selection([('tractor','Motorized Unit'), ('trailer','Trailer'), ('dolly','Dolly'), ('other','Other')], 'Unit Fleet Type', required=True),
# Pendiente de construir los objetos relacionados
#        'tires_number': openerp.osv.fields.integer('Number of Tires'),
#        'tires_extra': openerp.osv.fields.integer('Number of Extra Tires'),
#        'unit_status': openerp.osv.fields.many2one('tms.unit.fleet.unit.status', 'Unit Status', required=True),
#        'maint_cycle': openerp.osv.fields.many2one('tms.maintenance.cycle', 'Maintenance Cycle', required=True),
#        'avg_distance_per_day':openerp.osv.fields.float('Avg Distance per day', required=False, digits=(14,4), help='Specify average distance (mi./kms) per day for this unit'),
#        'fuel_efficiency_std':openerp.osv.fields.float('Fuel Efficiency', required=False, digits=(14,4), help='Fuel Efficiency as specified by the manufacturer'),
#        'maint_cycle_by':openerp.osv.fields.selection([('distance','Distance (mi./km)'), ('time','Time (Operation hours)')], 'Manage Maintenance Cycle by'),
#        'current_distance_score':openerp.osv.fields.float('Current Distance Score', required=False, digits=(14,4), help='Current Distance Score for this unit'),
#        'cumulative_distance_score':openerp.osv.fields.float('Cumulative Distance Score', required=False, digits=(14,4), help='Cumulative Distance Score for this unit'),
#        'last_maint_service': openerp.osv.fields.function(_get_last_maint_service, method=True, type="char", string='Last Maintenance Service'),
#        'next_maint_service': openerp.osv.fields.many2one('tms.maintenance.cycle.service', 'Next Maintenance ServiceCompany', required=False),
        
        
        'notes': openerp.osv.fields.text('Notes'),
        'active': openerp.osv.fields.boolean('Active'),
        'unit_extradata_ids' : openerp.osv.fields.one2many('tms.unit.extradata', 'unit_id', 'Extra Data'),
        'unit_expiry_ids' : openerp.osv.fields.one2many('tms.unit.expiry', 'unit_id', 'Expiry Extra Data'), 
        'unit_photo_ids' : openerp.osv.fields.one2many('tms.unit.photo', 'unit_id', 'Photos'), 
        'unit_active_history_ids' : openerp.osv.fields.one2many('tms.unit.active_history', 'unit_id', 'Active/Inactive History'), 
        'unit_red_tape_ids' : openerp.osv.fields.one2many('tms.unit.red_tape', 'unit_id', 'Unit Red Tapes'), 
        'supplier_unit': openerp.osv.fields.boolean('Supplier Unit'),
        'supplier_id': openerp.osv.fields.many2one('res.partner', 'Supplier', required=False, readonly=False, 
                                            domain="[('tms_category','=','none')]"),
        'latitude'      : openerp.osv.fields.float('Lat', required=False, digits=(20,10), help='GPS Latitude'),
        'longitude'     : openerp.osv.fields.float('Lng', required=False, digits=(20,10), help='GPS Longitude'),
#        'last_position' : openerp.osv.fields.char('Last Position', size=250),
    }

    _defaults = {
        'fleet_type' : lambda *a : 'tractor',
        'active': True,
    	}

    _sql_constraints = [
#            ('name_uniq', 'unique(name)', 'Unit name number must be unique !'),
            ('gps_id_uniq', 'unique(gps_id)', 'Unit GPS ID must be unique !'),
        ]

    def copy(self, cr, uid, id, default=None, context=None):
        unit = self.browse(cr, uid, id, context=context)
        if not default:
            default = {}
        default['name'] = unit['name'] + ' (copy)'
        default['gps_id'] = ''
        default['unit_extradata_ids'] = []
        default['unit_expiry_ids'] = []
        default['unit_photo_ids'] = []
        return super(fleet_vehicle, self).copy(cr, uid, id, default, context=context)


# Units PHOTOS
class fleet_vehicle_photo(osv.osv):
    _name = "tms.unit.photo"
    _description = "Units Photos"

    _columns = {
        'unit_id' : openerp.osv.fields.many2one('fleet.vehicle', 'Unit Name', required=True, ondelete='cascade'),
        'name': openerp.osv.fields.char('Description', size=64, required=True),
        'photo': openerp.osv.fields.binary('Photo'),
        }

    _sql_constraints = [
        ('name_uniq', 'unique(unit_id,name)', 'Photo name number must be unique for each unit !'),
        ]


fleet_vehicle_photo()


# Units EXTRA DATA
class fleet_vehicle_extradata(osv.osv):
    _name = "tms.unit.extradata"
    _description = "Extra Data for Units"
    _rec_name = "extra_value"

    _columns = {
        'unit_id'       : openerp.osv.fields.many2one('fleet.vehicle', 'Unit Name', required=True, ondelete='cascade', select=True,),        
        'extra_data_id' :openerp.osv.fields.many2one('tms.unit.category', 'Field', domain="[('type','=','extra_data')]", required=True),
        'extra_value'   : openerp.osv.fields.char('Valor', size=64, required=True),
        }

    _sql_constraints = [
        ('name_uniq', 'unique(unit_id,extra_data_id)', 'Extra Data Field must be unique for each unit !'),
        ]

fleet_vehicle_extradata()


# Units for Transportation EXPIRY EXTRA DATA
class fleet_vehicle_expiry(osv.osv):
    _name = "tms.unit.expiry"
    _description = "Expiry Extra Data for Units"

    _columns = {
        'unit_id'       : openerp.osv.fields.many2one('fleet.vehicle', 'Unit Name', required=True, ondelete='cascade', select=True,),        
        'expiry_id'     :openerp.osv.fields.many2one('tms.unit.category', 'Field', domain="[('type','=','expiry')]", required=True),
        'extra_value'   : openerp.osv.fields.date('Value', required=True),
        'name'          : openerp.osv.fields.char('Valor', size=10, required=True),
        }

    _sql_constraints = [
        ('name_uniq', 'unique(unit_id,expiry_id)', 'Expiry Data Field must be unique for each unit !'),
        ]

    def on_change_extra_value(self, cr, uid, ids, extra_value):
        return {'value': {'name': extra_value[8:] + '/' + extra_value[5:-3] + '/' + extra_value[:-6]}}


fleet_vehicle_expiry()




# Units Kits
class fleet_vehicle_kit(osv.osv):
    _name = "tms.unit.kit"
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _description = "Units Kits"

    _columns = {
        'name'          : openerp.osv.fields.char('Name', size=64, required=True),
        'unit_id'       : openerp.osv.fields.many2one('fleet.vehicle', 'Unit', required=True),
        'unit_type'     : openerp.osv.fields.related('unit_id', 'unit_type_id', type='many2one', relation='tms.unit.category', string='Unit Type', store=True, readonly=True),
        'trailer1_id'   : openerp.osv.fields.many2one('fleet.vehicle', 'Trailer 1', required=True),
        'trailer1_type' : openerp.osv.fields.related('trailer1_id', 'unit_type_id', type='many2one', relation='tms.unit.category', string='Trailer 1 Type', store=True, readonly=True),
        'dolly_id'      : openerp.osv.fields.many2one('fleet.vehicle', 'Dolly'),
        'dolly_type'    : openerp.osv.fields.related('dolly_id', 'unit_type_id', type='many2one', relation='tms.unit.category', string='Dolly Type', store=True, readonly=True),
        'trailer2_id'   : openerp.osv.fields.many2one('fleet.vehicle', 'Trailer 2'),
        'trailer2_type' : openerp.osv.fields.related('trailer2_id', 'unit_type_id', type='many2one', relation='tms.unit.category', string='Trailer 2 Type', store=True, readonly=True),
        'employee_id'   : openerp.osv.fields.many2one('hr.employee', 'Driver', domain=[('tms_category', '=', 'driver')]),
        'date_start'    : openerp.osv.fields.datetime('Date start', required=True),
        'date_end'      : openerp.osv.fields.datetime('Date end', required=True),
        'notes'         : openerp.osv.fields.text('Notes'),
        'active'            : openerp.osv.fields.boolean('Active'),        
        }

    _defaults = {
        'active' : lambda *a : True,
    }

    def _check_expiration(self, cr, uid, ids, context=None):
         
        for record in self.browse(cr, uid, ids, context=context):
            date_start = record.date_start
            date_end   = record.date_end
            
            sql = 'select name from fleet_vehicle_kit where id <> ' + str(record.id) + ' and unit_id = ' + str(record.unit_id.id) \
                    + ' and (date_start between \'' + date_start + '\' and \'' + date_end + '\'' \
                        + ' or date_end between \'' + date_start + '\' and \'' + date_end + '\');' 

            cr.execute(sql)
            data = filter(None, map(lambda x:x[0], cr.fetchall()))
            if len(data):
                raise osv.except_osv(_('Validity Error !'), _('You cannot have overlaping expiration dates for unit %s !\n' \
                                                                'This unit is overlaping Kit << %s >>')%(record.unit_id.name, data[0]))


            if record.dolly_id.id:
                sql = 'select name from fleet_vehicle_kit where id <> ' + str(record.id) + ' and dolly_id = ' + str(record.dolly_id.id) \
                        + ' and (date_start between \'' + date_start + '\' and \'' + date_end + '\'' \
                            + ' or date_end between \'' + date_start + '\' and \'' + date_end + '\');' 

                cr.execute(sql)
                data = filter(None, map(lambda x:x[0], cr.fetchall()))
                if len(data):
                    raise osv.except_osv(_('Validity Error !'), _('You cannot have overlaping expiration dates for dolly %s !\n' \
                                                                    'This dolly is overlaping Kit << %s >>')%(record.dolly_id.name, data[0]))

            sql = 'select name from fleet_vehicle_kit where id <> ' + str(record.id) + ' and (trailer1_id = ' + str(record.trailer1_id.id) + 'or trailer2_id = ' + str(record.trailer1_id.id) + ')' \
                    + ' and (date_start between \'' + date_start + '\' and \'' + date_end + '\'' \
                        + ' or date_end between \'' + date_start + '\' and \'' + date_end + '\');' 
            cr.execute(sql)
            data = filter(None, map(lambda x:x[0], cr.fetchall()))
            if len(data):
                raise osv.except_osv(_('Validity Error !'), _('You cannot have overlaping expiration dates for trailer %s !\n' \
                                                                'This trailer is overlaping Kit << %s >>')%(record.trailer1_id.name, data[0]))

            if record.trailer2_id.id:
                sql = 'select name from fleet_vehicle_kit where id <> ' + str(record.id) + ' and (trailer1_id = ' + str(record.trailer2_id.id) + 'or trailer2_id = ' + str(record.trailer2_id.id) + ')' \
                        + ' and (date_start between \'' + date_start + '\' and \'' + date_end + '\'' \
                            + ' or date_end between \'' + date_start + '\' and \'' + date_end + '\');' 

                cr.execute(sql)
                data = filter(None, map(lambda x:x[0], cr.fetchall()))  
                if len(data):
                    raise osv.except_osv(_('Validity Error !'), _('You cannot have overlaping expiration dates for trailer %s !\n' \
                                                                    'This trailer is overlaping Kit << %s >>')%(record.trailer2_id.name, data[0]))

            return True

    _constraints = [
        (_check_expiration,
            'The expiration is overlaping an existing Kit for this unit!',
            ['date_start'])
    ]

    _sql_constraints = [
        ('name_uniq', 'unique(unit_id,name)', 'Kit name number must be unique for each unit !'),
        ]
    _order = "name desc, date_start desc"


    def on_change_fleet_vehicle_id(self, cr, uid, ids, fleet_vehicle_id):
        res = {'value': {'date_start': time.strftime('%Y-%m-%d %H:%M')}}
        if not (fleet_vehicle_id):
            return res
        cr.execute("select date_end from fleet_vehicle_kit where id=%s order by  date_end desc limit 1", fleet_vehicle_id)
        date_start = cr.fetchall()
        if not date_start:
            return res
        else:
            return {'value': {'date_start': date_start[0]}} 


    def on_change_active(self, cr, uid, ids, active):
        if active:
            return {}
        return {'value': {'date_end' : time.strftime('%d/%m/%Y %H:%M:%S')}}


fleet_vehicle_kit()

#Unit Active / Inactive history
class fleet_vehicle_active_history(osv.osv):
    _name = "tms.unit.active_history"
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _description = "Units Active / Inactive history"

    _columns = {
        'state'             : openerp.osv.fields.selection([('draft','Draft'), ('confirmed','Confirmed'), ('cancel','Cancelled')], 'State', readonly=True),
        'unit_id'           : openerp.osv.fields.many2one('fleet.vehicle', 'Unit Name', required=True, ondelete='cascade', domain=[('active', 'in', ('true', 'false'))]),
        'unit_type_id'      : openerp.osv.fields.related('unit_id', 'unit_type_id', type='many2one', relation='tms.unit.category', store=True, string='Unit Type'),
        'prev_state'        : openerp.osv.fields.selection([('active','Active'), ('inactive','Inactive')], 'Previous State', readonly=True),
        'new_state'         : openerp.osv.fields.selection([('active','Active'), ('inactive','Inactive')], 'New State', readonly=True),
        'date'              : openerp.osv.fields.datetime('Date', states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)]}, required=True),
        'state_cause_id'    : openerp.osv.fields.many2one('tms.unit.category', 'Active/Inactive Cause', domain="[('type','=','active_cause')]", states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)]}, required=True),
        'name'              : openerp.osv.fields.char('Description', size=64, states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)]}, required=True),
        'notes'             : openerp.osv.fields.text('Notes', states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)]}, required=False),
        'create_uid'        : openerp.osv.fields.many2one('res.users', 'Created by', readonly=True),
        'create_date'       : openerp.osv.fields.datetime('Creation Date', readonly=True, select=True),
        'confirmed_by'      : openerp.osv.fields.many2one('res.users', 'Confirmed by', readonly=True),
        'date_confirmed'    : openerp.osv.fields.datetime('Date Confirmed', readonly=True),
        'cancelled_by'      : openerp.osv.fields.many2one('res.users', 'Cancelled by', readonly=True),
        'date_cancelled'    : openerp.osv.fields.datetime('Date Cancelled', readonly=True),

        }

    _defaults = {
        'state'     : lambda *a: 'draft',
        'date'      : lambda *a: time.strftime( DEFAULT_SERVER_DATETIME_FORMAT),
        }

    def on_change_state_cause_id(self, cr, uid, ids, state_cause_id):
        return {'value': {'name': self.pool.get('tms.unit.category').browse(cr, uid, [state_cause_id])[0].name }}

    def on_change_unit_id(self, cr, uid, ids, unit_id):
        val = {}
        if not unit_id:
            return  val
        for rec in self.pool.get('fleet.vehicle').browse(cr, uid, [unit_id]):
            val = {'value' : {'prev_state' : 'active' if rec.active else 'inactive','new_state' : 'inactive' if rec.active else 'active' } }
        return val

    def create(self, cr, uid, vals, context=None):
        values = vals
        if 'unit_id' in vals:
            res = self.search(cr, uid, [('unit_id', '=', vals['unit_id']),('state','=','draft')], context=None)
            if res and res[0]:
                raise osv.except_osv(
                        _('Warning!'),
                        _('You can not create a new record for this unit because theres is already a record for this unit in Draft State.'))
            unit_obj = self.pool.get('fleet.vehicle')
            for rec in unit_obj.browse(cr, uid, [vals['unit_id']]):
                vals.update({
                                'prev_state' : 'active' if rec.active else 'inactive',
                                'new_state'  : 'inactive' if rec.active else 'active' }
                            )
        print vals
        return super(fleet_vehicle_active_history, self).create(cr, uid, values, context=context)



    def unlink(self, cr, uid, ids, context=None):
        for rec in self.browse(cr, uid, ids):
            if rec.state == 'confirmed':
                raise osv.except_osv(
                        _('Warning!'),
                        _('You can not delete a record if is already Confirmed!!! Click Cancel button to continue.'))

        super(fleet_vehicle_active_history, self).unlink(cr, uid, ids, context=context)
        return True

    def action_cancel(self, cr, uid, ids, context=None):
        for rec in self.browse(cr, uid, ids):
            if rec.state == 'confirmed':
                raise osv.except_osv(
                        _('Warning!'),
                        _('You can not cancel a record if is already Confirmed!!!'))
        self.write(cr, uid, ids, {'state':'cancel', 'cancelled_by' : uid, 'date_cancelled':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        return True


    def action_confirm(self, cr, uid, ids, context=None):
        for rec in self.browse(cr, uid, ids):
            print rec.new_state == 'active'
            self.pool.get('fleet.vehicle').write(cr, uid, [rec.unit_id.id], {'active' : (rec.new_state == 'active')} )
        self.write(cr, uid, ids, {'state':'confirmed', 'confirmed_by' : uid, 'date_confirmed':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        return True


# Unit Red Tape
class fleet_vehicle_red_tape(osv.osv):
    _name = "tms.unit.red_tape"
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _description = "Units Red Tape history"

    _columns = {
        'state'             : openerp.osv.fields.selection([('draft','Draft'), ('pending','Pending'), ('progress','Progress'), ('done','Done'), ('cancel','Cancelled')], 'State', readonly=True),
        'unit_id'           : openerp.osv.fields.many2one('fleet.vehicle', 'Unit Name', required=True, ondelete='cascade', domain=[('active', 'in', ('true', 'false'))],
                                                            readonly=True, states={'draft':[('readonly',False)]} ),
        'unit_type_id'      : openerp.osv.fields.related('unit_id', 'unit_type_id', type='many2one', relation='tms.unit.category', store=True, string='Unit Type', readonly=True),
        'date'              : openerp.osv.fields.datetime('Date', required=True, readonly=True, states={'draft':[('readonly',False)], 'pending':[('readonly',False)]} ),
        'date_start'        : openerp.osv.fields.datetime('Date Start', readonly=True),
        'date_end'          : openerp.osv.fields.datetime('Date End', readonly=True),
        'red_tape_id'       : openerp.osv.fields.many2one('tms.unit.category', 'Red Tape', domain="[('type','=','red_tape')]",  required=True,
                                readonly=True, states={'draft':[('readonly',False)]} ),
        'partner_id'        : openerp.osv.fields.many2one('res.partner', 'Partner', states={'cancel':[('readonly',True)], 'done':[('readonly',True)]}, required=False),
        'name'              : openerp.osv.fields.char('Description', size=64, required=True, readonly=True, states={'draft':[('readonly',False)], 'pending':[('readonly',False)]} ),
        'notes'             : openerp.osv.fields.text('Notes', states={'cancel':[('readonly',True)], 'done':[('readonly',True)]}, required=False),
        'amount'            : openerp.osv.fields.float('Amount', required=True, digits_compute= dp.get_precision('Sale Price'), readonly=False, states={'cancel':[('readonly',True)], 'done':[('readonly',True)]} ),
        'amount_paid'       : openerp.osv.fields.float('Amount Paid', required=True, digits_compute= dp.get_precision('Sale Price'), readonly=False, states={'cancel':[('readonly',True)], 'done':[('readonly',True)]} ),
        'create_uid'        : openerp.osv.fields.many2one('res.users', 'Created by', readonly=True),
        'create_date'       : openerp.osv.fields.datetime('Creation Date', readonly=True, select=True),
        'pending_by'        : openerp.osv.fields.many2one('res.users', 'Pending by', readonly=True),
        'date_pending'      : openerp.osv.fields.datetime('Date Pending', readonly=True),
        'progress_by'       : openerp.osv.fields.many2one('res.users', 'Progress by', readonly=True),
        'date_progress'     : openerp.osv.fields.datetime('Date Progress', readonly=True),
        'done_by'           : openerp.osv.fields.many2one('res.users', 'Done by', readonly=True),
        'date_done'         : openerp.osv.fields.datetime('Date Done', readonly=True),
        'cancelled_by'      : openerp.osv.fields.many2one('res.users', 'Cancelled by', readonly=True),
        'date_cancelled'    : openerp.osv.fields.datetime('Date Cancelled', readonly=True),

        }

    _defaults = {
        'state'       : lambda *a: 'draft',
        'date'        : lambda *a: time.strftime( DEFAULT_SERVER_DATETIME_FORMAT),
        'amount'      : 0.0,
        'amount_paid' : 0.0,
        }

    def on_change_red_tape_id(self, cr, uid, ids, red_tape_id):
        return {'value': {'name': self.pool.get('tms.unit.category').browse(cr, uid, [red_tape_id])[0].name }}

    def create(self, cr, uid, vals, context=None):
        if 'unit_id' in vals:
            res = self.search(cr, uid, [('unit_id', '=', vals['unit_id']),('state','=','draft')], context=None)
            if res and res[0]:
                raise osv.except_osv(
                        _('Warning!'),
                        _('You can not create a new record for this unit because theres is already a record for this unit in Draft State.'))
        return super(fleet_vehicle_red_tape, self).create(cr, uid, vals, context=context)


    def unlink(self, cr, uid, ids, context=None):
        for rec in self.browse(cr, uid, ids):
            if rec.state == 'confirmed':
                raise osv.except_osv(
                        _('Warning!'),
                        _('You can not delete a record if is already Confirmed!!! Click Cancel button to continue.'))

        super(fleet_vehicle_active_history, self).unlink(cr, uid, ids, context=context)
        return True

    def action_cancel(self, cr, uid, ids, context=None):
        for rec in self.browse(cr, uid, ids):
            if rec.state == 'confirmed':
                raise osv.except_osv(
                        _('Warning!'),
                        _('You can not cancel a record if already Confirmed!!!'))
        self.write(cr, uid, ids, {'state':'cancel', 'cancelled_by' : uid, 'date_cancelled':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        return True

    def action_pending(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state':'pending', 'pending_by' : uid, 'date_pending':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        return True


    def action_progress(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state':'progress', 'progress_by' : uid, 
                                    'date_progress':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                                    'date_start':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
                                    })
        return True


    def action_done(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state':'done', 'done_by' : uid, 
                                'date_confirmed':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                                    'date_end':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
                                    })
        return True



# Causes for active / inactive transportation units   
# Pendiente

# Cities / Places
class tms_place(osv.osv):
    _name = 'tms.place'
    _description = 'Cities / Places'

    _columns = {
        'company_id'    : openerp.osv.fields.many2one('res.company', 'Company', required=False),
        'name'          : openerp.osv.fields.char('Place', size=64, required=True, select=True),
        'state_id'      : openerp.osv.fields.many2one('res.country.state', 'State Name', required=True),
        'country_id'    : openerp.osv.fields.related('state_id', 'country_id', type='many2one', relation='res.country', string='Country'),
        'latitude'      : openerp.osv.fields.float('Latitude', required=False, digits=(20,10), help='GPS Latitude'),
        'longitude'     : openerp.osv.fields.float('Longitude', required=False, digits=(20,10), help='GPS Longitude'),
        'route_ids'     : openerp.osv.fields.many2many('tms.route', 'tms_route_places_rel', 'place_id', 'route_id', 'Routes with this Place'),        
    }

    def  button_get_coords(self, cr, uid, ids, context=None):
        for rec in self.browse(cr, uid, ids):
            address = rec.name + "," + rec.state_id.name + "," + rec.country_id.name
            google_url = 'http://maps.googleapis.com/maps/api/geocode/json?address=' + address.encode('utf-8') + '&sensor=false'
            result = json.load(my_urllib.urlopen(google_url))
            print google_url
            print result
            if result['status'] == 'OK':
                print 'latitude: ', result['results'][0]['geometry']['location']['lat']
                print 'longitude: ', result['results'][0]['geometry']['location']['lng']
                self.write(cr, uid, ids, {'latitude': result['results'][0]['geometry']['location']['lat'], 'longitude' : result['results'][0]['geometry']['location']['lng'] })
            else:
                print result['status']
        return True


    def button_open_google(self, cr, uid, ids, context=None):
        for place in self.browse(cr, uid, ids):
            url="/tms/static/src/googlemaps/get_place_from_coords.html?" + str(place.latitude) + ','+ str(place.longitude)
        return { 'type': 'ir.actions.act_url', 'url': url, 'nodestroy': True, 'target': 'new' }
            
tms_place()


# Routes
class tms_route(osv.osv):
    _name ='tms.route'
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _description = 'Routes'
    
    _columns = {
        'company_id': openerp.osv.fields.many2one('res.company', 'Company', required=False),
        'name' : openerp.osv.fields.char('Route Name', size=64, required=True, select=True),
        'departure_id': openerp.osv.fields.many2one('tms.place', 'Departure', required=True),
        'arrival_id': openerp.osv.fields.many2one('tms.place', 'Arrival', required=True),
        'distance':openerp.osv.fields.float('Distance (mi./kms)', required=True, digits=(14,4), help='Route distance (mi./kms)'),
        'place_ids':openerp.osv.fields.many2many('tms.place', 'tms_route_places_rel', 'route_id', 'place_id', 'Places in this Route'),
        'travel_time':openerp.osv.fields.float('Travel Time (hrs)', required=True, digits=(14,4), help='Route travel time (hours)'),
        'route_fuelefficiency_ids' : openerp.osv.fields.one2many('tms.route.fuelefficiency', 'tms_route_id', 'Fuel Efficiency by Motor type'),
        'fuel_efficiency_drive_unit': openerp.osv.fields.float('Fuel Efficiency Drive Unit', required=False, digits=(14,4)),
        'fuel_efficiency_1trailer': openerp.osv.fields.float('Fuel Efficiency One Trailer', required=False, digits=(14,4)),
        'fuel_efficiency_2trailer': openerp.osv.fields.float('Fuel Efficiency Two Trailer', required=False, digits=(14,4)),
        'notes': openerp.osv.fields.text('Notes'),
        'active':openerp.osv.fields.boolean('Active'),

        }

    _defaults = {
        'active': True,
    }

    def  button_get_route_info(self, cr, uid, ids, context=None):
        for rec in self.browse(cr, uid, ids):
            if rec.departure_id.latitude and rec.departure_id.longitude and rec.arrival_id.latitude and rec.arrival_id.longitude:
                print context
                google_url = 'http://maps.googleapis.com/maps/api/distancematrix/json?origins=' + str(rec.departure_id.latitude) + ',' + str(rec.departure_id.longitude) + \
                                                                                '&destinations=' + str(rec.arrival_id.latitude) +',' + str(rec.arrival_id.longitude) + \
                                                                                '&mode=driving' + \
                                                                                '&language=' + context['lang'][:2] + \
                                                                                '&sensor=false'
                result = json.load(my_urllib.urlopen(google_url))
                if result['status'] == 'OK':
                    self.write(cr, uid, ids, {'distance': result['rows'][0]['elements'][0]['distance']['value'] / 1000.0, 'travel_time' : result['rows'][0]['elements'][0]['duration']['value'] / 3600.0 })
                else:
                    print result['status']
            else:
                raise osv.except_osv(_('Error !'), _('You cannot get route info because one of the places has no coordinates.'))

        return True


    def button_open_google(self, cr, uid, ids, context=None):
        for route in self.browse(cr, uid, ids):
            url="/tms/static/src/googlemaps/get_route.html?" + str(route.departure_id.latitude) + ','+ str(route.departure_id.longitude) + ',' + str(route.arrival_id.latitude) + ','+ str(route.arrival_id.longitude)
        return { 'type': 'ir.actions.act_url', 'url': url, 'nodestroy': True, 'target': 'new' }


    
tms_route()

# Route Fuel Efficiency by Motor
class tms_route_fuelefficiency(osv.osv):
    _name = "tms.route.fuelefficiency"
    _description = "Fuel Efficiency by Motor"

    _columns = {
        'tms_route_id' : openerp.osv.fields.many2one('tms.route', 'Route', required=True),        
        'motor_id':openerp.osv.fields.many2one('tms.unit.category', 'Motor', domain="[('type','=','motor')]", required=True),
        'type': openerp.osv.fields.selection([('tractor','Drive Unit'), ('one_trailer','Single Trailer'), ('two_trailer','Double Trailer')], 'Type', required=True),
        'performance' :openerp.osv.fields.float('Performance', required=True, digits=(14,4), help='Fuel Efficiency for this motor type'),
        }
    
    _sql_constraints = [
        ('route_motor_type_uniq', 'unique(tms_route_id, motor_id, type)', 'Motor + Type must be unique !'),
        ]

tms_route_fuelefficiency()


# Routes toll stations
class tms_route_tollstation(osv.osv):
    _name ='tms.route.tollstation'
    _description = 'Routes toll stations'
    
    _columns = {
        'company_id': openerp.osv.fields.many2one('res.company', 'Company', required=False),
        'name' : openerp.osv.fields.char('Name', size=64, required=True),
        'place_id':openerp.osv.fields.many2one('tms.place', 'Place', required=True),
        'partner_id':openerp.osv.fields.many2one('res.partner', 'Partner', required=True),
        'credit': openerp.osv.fields.boolean('Credit'),
        'tms_route_ids':openerp.osv.fields.many2many('tms.route', 'tms_route_tollstation_route_rel', 'route_id', 'tollstation_id', 'Routes with this Toll Station'),
        'active': openerp.osv.fields.boolean('Active'),
    }
   
    _defaults = {
        'active': True,
        }
    
tms_route_tollstation()

# Routes toll stations cost per axis
class tms_route_tollstation_costperaxis(osv.osv):
    _name ='tms.route.tollstation.costperaxis'
    _description = 'Routes toll stations cost per axis'

    _columns = {
        'tms_route_tollstation_id' : openerp.osv.fields.many2one('tms.route.tollstation', 'Toll Station', required=True),
        'unit_type_id':openerp.osv.fields.many2one('tms.unit.category', 'Unit Type', domain="[('type','=','unit_type')]", required=True),        
        'axis':openerp.osv.fields.integer('Axis', required=True),
        'cost_credit':openerp.osv.fields.float('Cost Credit', required=True, digits=(14,4)),
        'cost_cash':openerp.osv.fields.float('Cost Cash', required=True, digits=(14,4)),
        }
    
tms_route_tollstation_costperaxis()

# Routes toll stations INHERIT for adding cost per axis
class tms_route_tollstation(osv.osv):
    _inherit ='tms.route.tollstation'
    
    _columns = {
        'tms_route_tollstation_costperaxis_ids' : openerp.osv.fields.one2many('tms.route.tollstation.costperaxis', 'tms_route_tollstation_id', 'Toll Cost per Axis', required=True),
        }
    
tms_route_tollstation()


# Routes INHERIT for adding Toll Stations
class tms_route(osv.osv):
    _inherit ='tms.route'
    
    _columns = {
        'tms_route_tollstation_ids' : openerp.osv.fields.many2many('tms.route.tollstation', 'tms_route_tollstation_route_rel', 'tollstation_id', 'route_id', 'Toll Station in this Route'),
        }
    
tms_route()



# Route Fuel Efficiency by Motor
class tms_route_fuelefficiency(osv.osv):
    _name = "tms.route.fuelefficiency"
    _description = "Fuel Efficiency by Motor"

    _columns = {
        'tms_route_id' : openerp.osv.fields.many2one('tms.route', 'Route', required=True),        
        'motor_id':openerp.osv.fields.many2one('tms.unit.category', 'Motor', domain="[('type','=','motor')]", required=True),
        'type': openerp.osv.fields.selection([('tractor','Drive Unit'), ('one_trailer','Single Trailer'), ('two_trailer','Double Trailer')], 'Type', required=True),
        'performance' :openerp.osv.fields.float('Performance', required=True, digits=(14,4), help='Fuel Efficiency for this motor type'),
        }
    
    _sql_constraints = [
        ('route_motor_type_uniq', 'unique(tms_route_id, motor_id, type)', 'Motor + Type must be unique !'),
        ]

tms_route_fuelefficiency()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

