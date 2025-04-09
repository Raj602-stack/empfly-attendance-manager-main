from django.urls import path

from account.views import user_views, visitor_auth_view
from attendance.views import attendance_report, attendance_views, scan_views, present_by_default_views, kiosk_scan, ot_approval
from member.views import member_views, member_image_views, profile_views, member_upload_csv, member_report_view
from organization.views import org_views, org_location_views, system_location
from leave.views import approval_workflow_views, leave_views, leave_request_views
from roster.views import roster_views, location_views, cluster_views
from kiosk.views import kiosk_view
from visitor.views import visitation, visitation_report, visitor_views, confirm_visitation
from organization.views import upload_csv
from shift.views import shift_views, location_settings_view, applicability_settings_view, member_shift, shift_upload_csv
from export.views import export_request_views

urlpatterns = [
    path(
        "get-csrf/",
        user_views.get_csrf,
    ),
    # ! User
    path(
        "profile/",
        profile_views.MembersProfileAPI.as_view(),
    ),
    path(
        "user-registration/",
        user_views.UserRegistrationAPI.as_view(),
    ),
    path(
        "user-activation/",
        user_views.UserActivationAPI.as_view(),
    ),
    path(
        "set-password/",
        user_views.SetPasswordAPI.as_view(),
    ),
    # set password for members
    path(
        "set-password/<uuid:uuid>/",
        user_views.SetPasswordForMemberAPI.as_view(),
    ),
    path(
        "validate-password/",
        user_views.ValidatePasswordAPI.as_view(),
    ),
    path(
        "forgot-password/",
        user_views.ForgotPasswordAPI.as_view(),
    ),
    path(
        "password-reset/",
        user_views.PasswordResetAPI.as_view(),
    ),
    path(
        "test/",
        user_views.TestAPI.as_view(),
    ),
    path(
        "login/",
        user_views.LoginAPI.as_view(),
    ),
    path(
        "logout/",
        user_views.LogoutAPI.as_view(),
    ),
    path(
        "user-data/",
        user_views.UserDataAPI.as_view(),
    ),
    path(
        "switch-organizations/",
        user_views.SwitchOrganizationAPI.as_view(),
    ),
    path(
        "check-in-status/",
        member_views.CheckInStatusAPIView.as_view(),
    ),
    # ! Member
    path(
        "members/",
        member_views.AllMembersAPI.as_view(),
    ),
    path(
        "members/<uuid:uuid>/",
        member_views.MemberAPI.as_view(),
    ),
    path(
        "members/<uuid:uuid>/role/",
        member_views.MemberRoleAPI.as_view(),
    ),
    path(
        "members/<uuid:uuid>/manager/",
        member_views.MemberManagerAPI.as_view(),
    ),
    path(
        "members/<uuid:uuid>/designation/",
        member_views.MemberDesignationAPI.as_view(),
    ),
    path(
        "members/<uuid:uuid>/department/",
        member_views.MemberDepartmentAPI.as_view(),
    ),
    path(
        "members/<uuid:uuid>/cost-center/",
        member_views.MemberCostCenterAPI.as_view(),
    ),
    path(
        "members/<uuid:uuid>/rosters/",
        member_views.MemberRostesrAPI.as_view(),
    ),
    path(
        "members/images/",
        member_image_views.MembersAllImagesAPI.as_view(),
    ),
    path(
        "members/images/<uuid:uuid>/",
        member_image_views.MemberImageAPI.as_view(),
    ),

    path(
        "get-members-for-fr/",
        member_image_views.GetMemberForFrAPI.as_view(),
    ),

    path(
        "members/images/all/",
        member_image_views.AllMemberImages.as_view(),
    ),
    path(
        "members/images/all/<uuid:uuid>/",
        member_image_views.AllMemberImages.as_view(),
    ),
    path(
        "roles/",
        org_views.RolesAPI.as_view(),
    ),
    path(
        "departments/",
        org_views.AllDepartmentsAPI.as_view(),
    ),
    path(
        "departments/<uuid:uuid>/",
        org_views.DepartmentAPI.as_view(),
    ),
    path(
        "cost-centers/",
        org_views.AllCostCentersAPI.as_view(),
    ),
    path(
        "cost-centers/<uuid:uuid>/",
        org_views.CostCenterAPI.as_view(),
    ),
    path(
        "designations/",
        org_views.AllDesignationsAPI.as_view(),
    ),
    path(
        "designations/<uuid:uuid>/",
        org_views.DesignationAPI.as_view(),
    ),
    path(
        "holidays/",
        org_views.AllHolidaysAPI.as_view(),
    ),
    path(
        "holidays/all/",
        org_views.AllHolidaysListAPI.as_view(),
    ),
    path(
        "holidays/<uuid:uuid>/",
        org_views.HolidayAPI.as_view(),
    ),
    # path(
    #     "holidays/upload-csv/",
    #     org_views.HolidaysUploadCSVAPI.as_view(),
    # ),
    path(
        "org-locations/",
        org_location_views.AllOrgLocationsAPI.as_view(),
    ),
    path(
        "org-locations/<uuid:uuid>/",
        org_location_views.OrgLocationAPI.as_view(),
    ),
    # ! Attendance
    path(
        "attendance-report/",
        attendance_views.AttendanceReportAPI.as_view(),
    ),
    # path(
    #     "my-attendance/",
    #     attendance_views.MyAttendanceAPI.as_view(),
    # ),
    path(
        "present-by-default/all/",
        present_by_default_views.AllPresentByDefaultAPI.as_view(),
    ),
    path(
        "present-by-default/<uuid:uuid>/",
        present_by_default_views.PresentByDefaultAPI.as_view(),
    ),
    path(
        "present-by-default-members/",
        present_by_default_views.PresentByDefaultMembersAPI.as_view(),
    ),
    # path(
    #     "scans/",
    #     scan_views.ScansAPI.as_view(),
    # ),
    # path(
    #     "members/<uuid:uuid>/scans/",
    #     scan_views.MemberScansAPI.as_view(),
    # ),
    # ! Leave
    path(
        "leave-requests/",
        leave_request_views.AllLeaveRequestsAPI.as_view(),
    ),
    path(
        "my-leave-requests/",
        leave_request_views.MyLeaveRequestsAPI.as_view(),
    ),
    path(
        "leave-requests/<uuid:uuid>/",
        leave_request_views.LeaveRequestAPI.as_view(),
    ),
    path(
        "leave-requests/<uuid:uuid>/approve",
        leave_request_views.ApproveLeaveRequestAPI.as_view(),
    ),
    path(
        "leave-requests/<uuid:uuid>/activity/",
        leave_request_views.LeaveRequestActivityAPI.as_view(),
    ),
    path(
        "leave-types/",
        leave_views.AllLeaveTypesAPI.as_view(),
    ),
    path(
        "leave-types/<uuid:uuid>/",
        leave_views.LeaveTypeAPI.as_view(),
    ),
    path(
        "leave-types/<uuid:uuid>/applicability/",
        leave_views.LeaveApplicabilityAPI.as_view(),
    ),
    path(
        "leave-balances/",
        leave_views.AllLeaveBalancesAPI.as_view(),
    ),
    path(
        "members/leave-balances/",
        leave_views.MembersAllLeaveBalancesAPI.as_view(),
    ),
    path(
        "members/<uuid:uuid>/leave-balances/",
        leave_views.MembersLeaveBalanceAPI.as_view(),
    ),
    path(
        "approval-workflows/",
        approval_workflow_views.AllApprovalWorkflowsAPI.as_view(),
    ),
    path(
        "approval-workflow/<uuid:uuid>/",
        approval_workflow_views.ApprovalWorkflowAPI.as_view(),
    ),
    path(
        "approval-workflow/<uuid:uuid>/assign",
        approval_workflow_views.AssignApprovalWorkflowAPI.as_view(),
    ),
    # ! Roster
    # path(
    #     "clusters/",
    #     cluster_views.AllClustersAPI.as_view(),
    # ),

    # path(
    #     "clusters/upload-csv/",
    #     cluster_views.ClusterUploadAPI.as_view(),
    # ),

    # path(
    #     "clusters/<uuid:uuid>/",
    #     cluster_views.ClusterAPI.as_view(),
    # ),
    # path(
    #     "clusters/<uuid:uuid>/locations/",
    #     cluster_views.ClusterLocationsAPI.as_view(),
    # ),
    path(
        "locations/",
        location_views.AllLocationsAPI.as_view(),
    ),
    path(
        "locations/<uuid:uuid>/",
        location_views.LocationAPI.as_view(),
    ),
    path(
        "locations/upload-csv/",
        location_views.LocationsUploadCSVAPI.as_view(),
    ),
    # path(
    #     "rosters/",
    #     roster_views.AllRostersAPI.as_view(),
    # ),
    # path(
    #     "rosters/<uuid:uuid>/",
    #     roster_views.RosterAPI.as_view(),
    # ),
    # path(
    #     "rosters/<uuid:uuid>/members/",
    #     roster_views.RosterMembersAPI.as_view(),
    # ),
    # path(
    #     "rosters/calendar/",
    #     roster_views.RostersCalendarAPI.as_view(),
    # ),
    # path(
    #     "shifts/",
    #     shift_views.AllShiftsAPI.as_view(),
    # ),
    # path(
    #     "shifts/<uuid:uuid>/",
    #     shift_views.ShiftAPI.as_view(),
    # ),
    # path(
    #     "shifts-upload-csv/",
    #     shift_views.ShiftsUploadCSVAPI.as_view(),
    # ),
    path(
        "kiosks/",
        kiosk_view.AllKioskAPI.as_view(),
    ),
    path(
        "kiosks/<uuid:uuid>/",
        kiosk_view.KioskAPI.as_view(),
    ),

    path(
        "reset-kiosks/<uuid:uuid>/",
        kiosk_view.ResetKioskAPI.as_view(),
    ),

    path(
        "system-locations/",
        system_location.AllSystemLocationsAPI.as_view(),
    ),
    path(
        "system-locations/<uuid:uuid>/",
        system_location.SystemLocationAPI.as_view(),
    ),
    # ! visitor & visitations
    path(
        "visitors/",
        visitor_views.AllVisitorAPI.as_view(),
    ),
    path(
        "visitors/<uuid:uuid>/",
        visitor_views.VisitorAPI.as_view(),
    ),
    # Visitations for admin
    path(
        "visitation/register/all/",
        visitation.AllVisitationRegisterAPI.as_view(),
    ),
    # all visitation for admin and hr
    path(
        "visitations/all/",
        visitation.GetAllVisitationAPI.as_view(),
    ),
    path(
        "visitation-created-by/",
        visitation.AllUsersCreatedVisitationAPI.as_view(),
    ),
    # for member, hr, admin
    path(
        "visitations/",
        visitation.AllVisitationAPI.as_view(),
    ),
    path(
        "visitations/<uuid:uuid>/",
        visitation.VisitationAPI.as_view(),
    ),

    #  Visitation flow for visitor.
    path(
        "visitations/visitor/",
        visitation.VisitorVisitationAPI.as_view(),
    ),
    path(
        "visitations/visitor/<uuid:uuid>/",
        visitation.AllVisitorVisitationAPI.as_view(),
    ),
    path(
        "visitations/confirm/",
        visitation.VisitationConfirmationAPI.as_view(),
    ),
    # create visitor a/c as visitor
    path(
        "visitor-registration/",
        visitor_views.AllVisitorRegisterAPI.as_view(),
    ),
    # create scan
    path(
        "visitation-scan/",
        visitation.VisitationScanAPI.as_view(),
    ),
    path(
        "visitor/otp/",
        visitor_auth_view.VisitorOtpAPI.as_view(),
    ),
    # visitor login
    path(
        "visitor/verify/otp/",
        visitor_auth_view.VisitorVerifyOtpAPI.as_view(),
    ),
    path(
        "visitor/logout/",
        visitor_auth_view.VisitorLogoutAPI.as_view(),
    ),
    # path(
    #     "visitation-report/",
    #     visitation.VisitationReportAPI.as_view(),
    # ),
    path(
        "host/allowed-to-meet/",
        member_views.HostAllowedToMeetAPI.as_view(),
    ),
    # upload csv
    path(
        "members/upload-csv/",
        member_upload_csv.MembersUploadCSVAPI.as_view(),
    ),
    path(
        "departments/upload-csv/",
        upload_csv.DepartmentUploadCSVAPI.as_view(),
    ),
    path(
        "system-locations/upload-csv/",
        upload_csv.SystemLocationsUploadCSVAPI.as_view(),
    ),
    path(
        "designations/upload-csv/",
        upload_csv.DesignationUploadCSVAPI.as_view(),
    ),
    path(
        "visitors/upload-csv/",
        upload_csv.VisitorUploadCSVAPI.as_view(),
    ),
    # path(
    #     "shift/<uuid:uuid>/location-settings/",
    #     location_settings_view.ShiftLocationSettingsAPI.as_view(),
    # ),
    path(
        "shift/<uuid:uuid>/applicability-settings/",
        applicability_settings_view.AllApplicabilitySettingsAPI.as_view(),
    ),
    path("applicability-settings-priority/",
        org_views.ApplicabilitySettingsPriorityAPI.as_view()
    ),
    path("check-shift-override/",
        location_settings_view.CheckShiftExistAsFK.as_view()
    ),
    path("shift-calendar/",
        shift_views.ShiftCalendarAPI.as_view()
    ),

    # Accept/Decline visitation for logged in user
    path("visitations/confirm/<uuid:uuid>/",
        confirm_visitation.AllVisitationConfirmAPI.as_view()
    ),

    path("scans/",
        scan_views.CheckInOrCheckoutAPI.as_view()
    ),
    path("attendance/is-checkin/",
        scan_views.IsCheckInAPI.as_view()
    ),

    # attendance register page
    path("member-scans/all/", scan_views.AllMemberScansAPI.as_view()),

    path("today-shift/", member_shift.TodayShiftAPI.as_view()),

    # Logged in user member scans
    path("member-scans/", scan_views.MyMemberScansAPI.as_view()),

    path(
        "organization/",
        org_views.OrganizationAPI.as_view(),
    ),

    path(
        "organization/kiosk-management-settings/",
        org_views.OrgKioskManagementAPI.as_view(),
    ),

    path(
        "organization/shift-management-settings/",
        org_views.OrganizationShiftManagementSettingsAPI.as_view(),
    ),
    path(
        "organization/visitor-management/",
        org_views.OrganizationVisitorManagementSettingsAPI.as_view(),
    ),
    path(
        "timezones/",
        org_views.TimeZonesAPIView.as_view(),
    ),
    path(
        "employee-shift-mapping/",
        shift_views.EmployeeShiftMappingAPI.as_view(),
    ),
    path(
        "employee-shift-mapping/<uuid:uuid>/",
        shift_views.AllEmployeeShiftMappingAPI.as_view(),
    ),
    path(
        "employee/shift-schedule-logs/<uuid:uuid>/",
        shift_views.EmployeeShiftScheduleLogAPI.as_view(),
    ),
    path(
        "export-requests/poll/<uuid:uuid>/",
        export_request_views.PollExportRequestAPI.as_view(),
    ),
    path(
        "shifts/",
        shift_views.AllShiftsAPI.as_view(),
    ),
    path(
        "shifts/<uuid:uuid>/",
        shift_views.ShiftsAPI.as_view(),
    ),
    path(
        "location-settings/",
        location_settings_view.LocationSettingsAPI.as_view(),
    ),

    path(
        "location-settings/<uuid:uuid>/",
        location_settings_view.AllLocationSettingsAPI.as_view(),
    ),
    path(
        "location-settings/upload-csv/",
        shift_upload_csv.LocationSettingsUploadCSVAPI.as_view(),
    ),


    path(
        "deactivate-shift/",
        shift_views.DeActivateShiftAPI.as_view(),
    ),
    path(
        "fetch-file/<path:path>/",
        user_views.FetchFileAPI.as_view(),
    ),
    # path(
    #     "fetch-file/<path:path>",
    #     user_views.FetchFileAPI.as_view(),
    # ),
    path(
        "dashboard/",
        member_report_view.DashboardAPI.as_view(),
        name="api-dashboard-view",
    ),
    path(
        "kiosk-access/<uuid:uuid>/",
        kiosk_scan.KioskAccessAPI.as_view(),
    ),

    path(
        "kiosk/logout/<uuid:uuid>/",
        kiosk_scan.KioskLogoutAPI.as_view(),
    ),

    path(
        "scans/kiosk/<uuid:uuid>/",
        kiosk_scan.KioskScanAPI.as_view(),
    ),


    path(
        "members/status/<uuid:uuid>/",
        member_views.ActivateMemberAPI.as_view(),
    ),
    path(
        "shift/activate/<uuid:uuid>/",
        shift_views.ActivateShiftAPI.as_view(),
    ),

    # attendance Report
    path(
        "report/attendance-status/",
        attendance_report.MemberAttendanceReportAPI.as_view(),
    ),

    path(
        "report/attendance-curr-day-status/",
        attendance_report.MemberCheckInStatusAPI.as_view(),
    ),



    # Visitation Report
    path(
        "report/visitation-status/",
        visitation_report.VisitorScanReportAPI.as_view(),
    ),

    path(
        "report/visitation-register-curr-day-status/",
        visitation_report.VisitorCurrDayStatus.as_view(),
    ),

    path(
        "holidays/upload-csv/",
        upload_csv.HolidaysUploadCSVAPI.as_view(),
    ),

    path(
        "ot-request/",
        ot_approval.OtRequestAPI.as_view(),
    ),

    path(
        "members-data/",
        member_views.AllMembersDataAPI.as_view(),
    ),

    path(
        "my-attendance/",
        attendance_views.MyAttendanceReportAPI.as_view(),
    ),
    path(
        "my-attendance/<int:id>/",
        attendance_views.GetMyAttendanceObjAPI.as_view(),
    ),

    path(
        "raise-ot/",
        ot_approval.RaiseOTAPI.as_view(),
    ),
]
