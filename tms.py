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

# Master catalog used for:
# - Unit Types
# - Unit Brands
# - Unit / Motor Models
# - Motor Type
# - Extra Data for Units (Like Insurance Policy, Unit Invoice, etc
# - Unit Status (Still not defined if is keeped or not
# - Documentacion expiraton  for Transportation Units
class tms_unit_category(osv.osv):
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
                            ('brand','Brand'), 
                            ('model','Model'), 
                            ('motor','Motor'), 
                            ('extra_data', 'Extra Data'),
                            ('unit_status','Unit Status'),
                            ('expiry','Expiry'),
                        ], 'Category Type',required=True, help="""Category Types:
 - View: Use this to define tree structure
 - Type: Use this to define Unit types, like Tractor, Trailers, dolly, van, etc.
 - Brand: Units brands
 - Model: Unit Models
 - Motor: Motors
 - Extra Data: Use to define several extra fields for unit catalog.
 - Expiry: Use ti define several extra fields for unit catalog related to document expiration.
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
            cr.execute('select distinct parent_id from tms_unit_category where id IN %s',(tuple(ids),))
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
        return super(tms_unit_category, self).copy(cr, uid, id, default, context=context)

tms_unit_category()

                             
# Units for Transportation
class tms_unit(osv.osv):
    _name = "tms.unit"
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _description = "All motor/trailer units"

    _columns = {
        'shop_id': openerp.osv.fields.many2one('sale.shop', 'Shop', required=True, readonly=False),
        'company_id': openerp.osv.fields.related('shop_id','company_id',type='many2one',relation='res.company',string='Company',store=True,readonly=True),
        'name': openerp.osv.fields.char('Unit Name', size=64, required=True),
        'year_model':openerp.osv.fields.char('Year Model', size=64), 
        'unit_type_id':openerp.osv.fields.many2one('tms.unit.category', 'Unit Type', domain="[('type','=','unit_type')]"),
        'unit_brand_id':openerp.osv.fields.many2one('tms.unit.category', 'Brand', domain="[('type','=','brand')]"),
        'unit_model_id':openerp.osv.fields.many2one('tms.unit.category', 'Model', domain="[('type','=','model')]"),
        'unit_motor_id':openerp.osv.fields.many2one('tms.unit.category', 'Motor', domain="[('type','=','motor')]"),
        'serial_number': openerp.osv.fields.char('Serial Number', size=64),
        'vin': openerp.osv.fields.char('VIN', size=64),
        'plates': openerp.osv.fields.char('Plates', size=64),
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
        'employee_id': openerp.osv.fields.many2one('hr.employee', 'Driver', required=False, domain=[('tms_category', '=', 'driver')]),
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
        'supplier_unit': openerp.osv.fields.boolean('Supplier Unit'),
        'supplier_id': openerp.osv.fields.many2one('res.partner', 'Supplier', required=False, readonly=False, 
                                            domain="[('tms_category','=','none')]"),
    }

    _defaults = {
        'fleet_type' : lambda *a : 'tractor',
        'active': True,
    	}

    _sql_constraints = [
            ('name_uniq', 'unique(name)', 'Unit name number must be unique !'),
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
        return super(tms_unit, self).copy(cr, uid, id, default, context=context)

tms_unit()

# Units PHOTOS
class tms_unit_photo(osv.osv):
    _name = "tms.unit.photo"
    _description = "Units Photos"

    _columns = {
        'unit_id' : openerp.osv.fields.many2one('tms.unit', 'Unit Name', required=True, ondelete='cascade'),
        'name': openerp.osv.fields.char('Description', size=64, required=True),
        'photo': openerp.osv.fields.binary('Photo'),
        }

    _sql_constraints = [
        ('name_uniq', 'unique(unit_id,name)', 'Photo name number must be unique for each unit !'),
        ]


tms_unit_photo()


# Units EXTRA DATA
class tms_unit_extradata(osv.osv):
    _name = "tms.unit.extradata"
    _description = "Extra Data for Units"
    _rec_name = "extra_value"

    _columns = {
        'unit_id'       : openerp.osv.fields.many2one('tms.unit', 'Unit Name', required=True, ondelete='cascade', select=True,),        
        'extra_data_id' :openerp.osv.fields.many2one('tms.unit.category', 'Field', domain="[('type','=','extra_data')]", required=True),
        'extra_value'   : openerp.osv.fields.char('Valor', size=64, required=True),
        }

    _sql_constraints = [
        ('name_uniq', 'unique(unit_id,extra_data_id)', 'Extra Data Field must be unique for each unit !'),
        ]

tms_unit_extradata()


# Units for Transportation EXPIRY EXTRA DATA
class tms_unit_expiry(osv.osv):
    _name = "tms.unit.expiry"
    _description = "Expiry Extra Data for Units"

    _columns = {
        'unit_id'       : openerp.osv.fields.many2one('tms.unit', 'Unit Name', required=True, ondelete='cascade', select=True,),        
        'expiry_id'     :openerp.osv.fields.many2one('tms.unit.category', 'Field', domain="[('type','=','expiry')]", required=True),
        'extra_value'   : openerp.osv.fields.date('Value', required=True),
        'name'          : openerp.osv.fields.char('Valor', size=10, required=True),
        }

    _sql_constraints = [
        ('name_uniq', 'unique(unit_id,expiry_id)', 'Expiry Data Field must be unique for each unit !'),
        ]

    def on_change_extra_value(self, cr, uid, ids, extra_value):
        return {'value': {'name': extra_value[8:] + '/' + extra_value[5:-3] + '/' + extra_value[:-6]}}


tms_unit_expiry()




# Units Kits
class tms_unit_kit(osv.osv):
    _name = "tms.unit.kit"
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _description = "Units Kits"

    _columns = {
        'name'          : openerp.osv.fields.char('Name', size=64, required=True),
        'unit_id'       : openerp.osv.fields.many2one('tms.unit', 'Unit', required=True),
        'unit_type'     : openerp.osv.fields.related('unit_id', 'unit_type_id', type='many2one', relation='tms.unit.category', string='Unit Type', store=True, readonly=True),
        'trailer1_id'   : openerp.osv.fields.many2one('tms.unit', 'Trailer 1', required=True),
        'trailer1_type' : openerp.osv.fields.related('trailer1_id', 'unit_type_id', type='many2one', relation='tms.unit.category', string='Trailer 1 Type', store=True, readonly=True),
        'dolly_id'      : openerp.osv.fields.many2one('tms.unit', 'Dolly'),
        'dolly_type'    : openerp.osv.fields.related('dolly_id', 'unit_type_id', type='many2one', relation='tms.unit.category', string='Dolly Type', store=True, readonly=True),
        'trailer2_id'   : openerp.osv.fields.many2one('tms.unit', 'Trailer 2'),
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
            
            sql = 'select name from tms_unit_kit where id <> ' + str(record.id) + ' and unit_id = ' + str(record.unit_id.id) \
                    + ' and (date_start between \'' + date_start + '\' and \'' + date_end + '\'' \
                        + ' or date_end between \'' + date_start + '\' and \'' + date_end + '\');' 

            cr.execute(sql)
            data = filter(None, map(lambda x:x[0], cr.fetchall()))
            if len(data):
                raise osv.except_osv(_('Validity Error !'), _('You cannot have overlaping expiration dates for unit %s !\n' \
                                                                'This unit is overlaping Kit << %s >>')%(record.unit_id.name, data[0]))


            if record.dolly_id.id:
                sql = 'select name from tms_unit_kit where id <> ' + str(record.id) + ' and dolly_id = ' + str(record.dolly_id.id) \
                        + ' and (date_start between \'' + date_start + '\' and \'' + date_end + '\'' \
                            + ' or date_end between \'' + date_start + '\' and \'' + date_end + '\');' 

                cr.execute(sql)
                data = filter(None, map(lambda x:x[0], cr.fetchall()))
                if len(data):
                    raise osv.except_osv(_('Validity Error !'), _('You cannot have overlaping expiration dates for dolly %s !\n' \
                                                                    'This dolly is overlaping Kit << %s >>')%(record.dolly_id.name, data[0]))

            sql = 'select name from tms_unit_kit where id <> ' + str(record.id) + ' and (trailer1_id = ' + str(record.trailer1_id.id) + 'or trailer2_id = ' + str(record.trailer1_id.id) + ')' \
                    + ' and (date_start between \'' + date_start + '\' and \'' + date_end + '\'' \
                        + ' or date_end between \'' + date_start + '\' and \'' + date_end + '\');' 
            cr.execute(sql)
            data = filter(None, map(lambda x:x[0], cr.fetchall()))
            if len(data):
                raise osv.except_osv(_('Validity Error !'), _('You cannot have overlaping expiration dates for trailer %s !\n' \
                                                                'This trailer is overlaping Kit << %s >>')%(record.trailer1_id.name, data[0]))

            if record.trailer2_id.id:
                sql = 'select name from tms_unit_kit where id <> ' + str(record.id) + ' and (trailer1_id = ' + str(record.trailer2_id.id) + 'or trailer2_id = ' + str(record.trailer2_id.id) + ')' \
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


    def on_change_tms_unit_id(self, cr, uid, ids, tms_unit_id):
        res = {'value': {'date_start': time.strftime('%Y-%m-%d %H:%M')}}
        if not (tms_unit_id):
            return res
        cr.execute("select date_end from tms_unit_kit where id=%s order by  date_end desc limit 1", tms_unit_id)
        date_start = cr.fetchall()
        if not date_start:
            return res
        else:
            return {'value': {'date_start': date_start[0]}} 


    def on_change_active(self, cr, uid, ids, active):
        if active:
            return {}
        return {'value': {'date_end' : time.strftime('%d/%m/%Y %H:%M:%S')}}


tms_unit_kit()




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
        'latitude'      : openerp.osv.fields.float('Latitude', required=False, digits=(14,10), help='GPS Latitude'),
        'longitude'     : openerp.osv.fields.float('Longitude', required=False, digits=(14,10), help='GPS Longitude'),
        'route_ids'     : openerp.osv.fields.many2many('tms.route', 'tms_route_places_rel', 'place_id', 'route_id', 'Routes with this Place'),
    }

    def button_open_google(self, cr, uid, ids, context=None):
        for place in self.browse(cr, uid, ids):
            url="http://www.google.com"
#            url="http://localhost:8069/web/static/src/googlemaps/get_coords_from_place.html?" + place.name + ','+ place.state_id.name+','+ place.country_id.name
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

