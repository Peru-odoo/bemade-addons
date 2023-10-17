from odoo import models, fields, _, api
from odoo.exceptions import ValidationError
from datetime import date
from dateutil.relativedelta import relativedelta


class Patient(models.Model):
    _name = 'sports.patient'
    _description = "Patient at a sports medicine clinic."
    _inherit = ['mail.thread', 'mail.activity.mixin']

    first_name = fields.Char(required=True)
    last_name = fields.Char(required=True)
    name = fields.Char(compute="_compute_name")
    date_of_birth = fields.Date(
        groups="bemade_sports_clinic.group_sports_clinic_treatment_professional")
    age = fields.Integer(compute='_compute_age',
                         groups="bemade_sports_clinic.group_sports_clinic_treatment_professional")
    phone = fields.Char(unaccent=False,
                        groups="bemade_sports_clinic.group_sports_clinic_user")
    email = fields.Char(groups="bemade_sports_clinic.group_sports_clinic_user")
    contact_ids = fields.One2many(comodel_name='sports.patient.contact',
                                  inverse_name='patient_id', string='Patient Contacts',
                                  groups="bemade_sports_clinic.group_sports_clinic_user")
    team_ids = fields.Many2many(comodel_name='res.partner',
                                relation='sports_team_patient_rel',
                                column1='patient_id',
                                column2='team_id',
                                string='Teams',
                                domain=[('type', '=', 'team')])
    player_status = fields.Selection([
        ('practice', 'Practice'),
        ('match', 'Match'),
    ])
    injury_ids = fields.One2many(comodel_name='sports.patient.injury',
                                 inverse_name='patient_id',
                                 string='Injuries', )
    predicted_return_date = fields.Date(compute='_compute_predicted_return_date', )
    is_injured = fields.Boolean(compute='_compute_is_injured')
    injured_since = fields.Date(compute='_compute_is_injured')

    # authorized_users = fields.One2many(compute='_compute_authorized_users', store=True)
    #
    # @api.depends('injury_ids.treatment_professional_ids', 'team_ids.staff_team_ids',
    #              'message_follower_ids')
    # def _compute_authorized_users(self):
    #     for rec in self:
    #         auth_users = self.env['res.users'].search(['|', ('partner_id', 'in',
    #             rec.injury_ids.mapped('treatment_professional_ids').ids),
    #             '|', ('partner_id', 'in', rec.team_ids.mapped('staff_team_ids').ids),
    #                  ('partner_id', 'in', rec.message_follower_ids.ids)])

    @api.depends('date_of_birth')
    def _compute_age(self):
        for rec in self:
            if not rec.date_of_birth:
                rec.age = False
            else:
                rec.age = relativedelta(date.today(), rec.date_of_birth).years

    @api.depends('injury_ids.predicted_return_date')
    def _compute_predicted_return_date(self):
        for rec in self:
            ongoing_injuries = rec.injury_ids.filtered(
                lambda r: r.predicted_return_date > date.today()).sorted(
                'predicted_return_date')
            if ongoing_injuries:
                rec.predicted_return_date = ongoing_injuries[-1]. \
                    predicted_return_date
            else:
                rec.predicted_return_date = False

    @api.depends('first_name', 'last_name')
    def _compute_name(self):
        for rec in self:
            rec.name = ((rec.first_name or "") + " " + (rec.last_name or
                                                        "")).strip()

    @api.depends('injury_ids.is_resolved')
    def _compute_is_injured(self):
        injured = self.filtered(
            lambda r: r.injury_ids.filtered(lambda i: not i.is_resolved))
        for rec in injured:
            rec.is_injured = True
            rec.injured_since = rec.injury_ids.sorted('injury_date_time')[
                -1].injury_date_time.date()
        for rec in self - injured:
            rec.is_injured = False
            rec.injured_since = False


class PatientContact(models.Model):
    _name = 'sports.patient.contact'
    _description = "Emergency or other contacts for a patient."

    sequence = fields.Integer(required=True, default=0)
    name = fields.Char(unaccent=False)
    contact_type = fields.Selection(selection=[
        ('Mother', 'mother'),
        ('Father', 'father'),
        ('other', 'Other'),
    ])
    phone = fields.Char(unaccent=False)
    patient_id = fields.Many2one(comodel_name='sports.patient', string="Patient")


class PatientInjury(models.Model):
    _name = 'sports.patient.injury'
    _description = "A patient's injury."
    _inherit = ['mail.thread', 'mail.activity.mixin']

    patient_id = fields.Many2one(comodel_name='sports.patient',
                                 string="Patient",
                                 readonly=True)
    patient_name = fields.Char(related="patient_id.name")
    diagnosis = fields.Char(tracking=True)
    injury_date_time = fields.Datetime(string='Date and Time of Injury')
    internal_notes = fields.Html(tracking=True)
    treatment_professional_ids = fields.Many2many(comodel_name='res.partner',
                                                  relation='patient_injury_treatment_pro_rel',
                                                  column1='patient_injury_id',
                                                  column2='treatment_pro_id',
                                                  string='Treatment Professionals',
                                                  domain=[
                                                      ('is_treatment_professional', '=',
                                                       True)], )
    predicted_return_date = fields.Date(tracking=True)
    is_resolved = fields.Boolean(compute="_compute_is_resolved")

    def write(self, vals):
        super().write(vals)
        if 'treatment_professional_ids' in vals:
            to_subscribe = (self.treatment_professional_ids
                            - self.message_follower_ids.mapped('partner_id'))
            self.message_subscribe(to_subscribe.ids)

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        for rec in res:
            to_subscribe = (rec.treatment_professional_ids
                            - rec.message_follower_ids.mapped('partner_id'))
            rec.message_subscribe(to_subscribe.ids)
        return res

    @api.depends('predicted_return_date')
    def _compute_is_resolved(self):
        to_compute = self.filtered(lambda r: r.predicted_return_date)
        for rec in to_compute:
            rec.is_resolved = rec.predicted_return_date < date.today()
        (self - to_compute).is_resolved = False
