# from django.db import IntegrityError
# from export.utils import create_export_request
# from organization.models import Organization, SystemLocation
# from rest_framework import views, status
# from rest_framework.response import Response
# from rest_framework.permissions import IsAuthenticated

# from django.shortcuts import get_object_or_404
# from django.db.models.deletion import ProtectedError
# from django.core.exceptions import ValidationError
# from django.core.paginator import Paginator
# from django.db.models import Q
# from utils.response import HTTP_200
# from utils.utils import HTTP_400

# from api import permissions
# from member.models import Member
# from roster.models import Cluster, Location

# # TODO Shift
# # from roster.models import Cluster, Location, Shift, Roster
# from roster import serializers
# from roster.search import search_clusters
# from roster.utils import get_cluster
# from utils import read_data, fetch_data, create_data, email_funcs
# from export import utils as export_utils

# import logging


# logger = logging.getLogger(__name__)


# class AllClustersAPI(views.APIView):

#     permission_classes = [permissions.IsTokenAuthenticated]
#     serializer_class = serializers.ClusterSerializer

#     def get(self, request, *args, **kwargs):

#         org_uuid = request.headers.get("organization-uuid")
#         org = fetch_data.get_organization(request.user, org_uuid)
#         member = fetch_data.get_member(request.user, org.uuid)

#         if fetch_data.is_admin_or_hr(member) is False:
#             return read_data.get_403_response()

#         clusters = org.clusters.all()
#         search_query = request.GET.get("search")
#         clusters = search_clusters(clusters, search_query)

#         cluster_status = request.GET.get("status", "active")
#         if cluster_status in ("active", "inactive"):
#             clusters = clusters.filter(status=cluster_status)

#         if bool(request.GET.get("export_csv")) is True:
#             if not clusters.exists():
#                 return HTTP_400({}, {"message": "No data found for export."})

#             cluster_uuids = export_utils.get_uuid_from_qs(clusters)
#             export_request = create_export_request(member, "cluster", cluster_uuids)
#             if export_request is None:
#                 return HTTP_400({}, {"export_request_uuid": None})
#             return HTTP_200({"export_request_uuid": export_request.uuid})


#         per_page = request.GET.get("per_page", 10)
#         page = request.GET.get("page", 1)
#         paginator = Paginator(clusters, per_page)
#         page_obj = paginator.get_page(page)

#         serializer = self.serializer_class(page_obj.object_list, many=True)
#         return Response(
#             {
#                 "data": serializer.data,
#                 "pagination": {"total_pages": paginator.num_pages, "page": page},
#             },
#             status=status.HTTP_200_OK,
#         )

#     def post(self, request, *args, **kwargs):
#         """ Cluster manager and system location can belongs to multiple cluster

#         """

#         org_uuid = request.headers.get("organization-uuid")
#         org = fetch_data.get_organization(request.user, org_uuid)
#         member = fetch_data.get_member(request.user, org.uuid)

#         if fetch_data.is_admin_or_hr(member) is False:
#             return read_data.get_403_response()

#         name = request.data.get("name")
#         description = request.data.get("description")
#         location_uuids = request.data.get("location_uuids", [])
#         manager_uuids = request.data.get("manager_uuids", [])
#         cluster_status = request.data.get("status")
#         print(cluster_status)

#         if not name:
#             return HTTP_400({}, {"message": "Name is required."})

#         if not location_uuids:
#             return HTTP_400({}, {"message": "Location is required."})

#         if not manager_uuids:
#             return HTTP_400({}, {"message": "Manager is required."})

#         if cluster_status not in ("active", "inactive"):
#             return HTTP_400({}, {"message": "Cluster status must be active/inactive."})

#         # * Location

#         try:
#             system_location = SystemLocation.objects.filter(
#                 organization=org, uuid__in=location_uuids, status="active"
#             )
#             is_selected_system_location = system_location.exists()
#         except (ValidationError) as err:
#             logger.error(err)
#             return Response(
#                 {"message": "Enter valid UUID(s)"}, status=status.HTTP_400_BAD_REQUEST
#             )

#         # exclude_loc_ids = []
#         # for location in system_location:
#         #     if location.cluster.exists():
#         #         exclude_loc_ids.append(location.id)

#         # if exclude_loc_ids:
#         #     system_location = system_location.exclude(id__in=exclude_loc_ids)

#         if is_selected_system_location and system_location.exists() is False:
#             return HTTP_400({}, {"message": "Selected system location are inactive."})
#         if not system_location.exists():
#             return read_data.get_404_response("System Location(s)")

#         # * Manager
#         try:
#             managers = Member.objects.filter(
#                 organization=org, uuid__in=manager_uuids, status="active"
#             )
#             is_selected_manager = managers.exists()
#         except (ValidationError) as err:
#             logger.error(err)
#             return Response(
#                 {"message": "Enter valid UUID(s)"}, status=status.HTTP_400_BAD_REQUEST
#             )

#         # exclude_manager_ids = []
#         # for manager in managers:
#         #     if manager.clusters.exists():
#         #         exclude_manager_ids.append(manager.id)

#         # if exclude_manager_ids:
#         #     managers = managers.exclude(id__in=exclude_manager_ids)

#         if is_selected_manager and not managers.exists():
#             return HTTP_400({}, {"message": "Selected managers are inactive."})
#         if not managers.exists():
#             return read_data.get_404_response("Member(s)")

#         try:
#             cluster = Cluster.objects.create(
#                 name=name, description=description, organization=org, status=cluster_status
#             )
#         except IntegrityError as err:
#             return read_data.get_409_response("Cluster", "name")
#         except Exception as err:
#             logger.error(err)
#             logger.exception(
#                 f"Add exception for {e.__class__.__name__} in AllClustersAPI"
#             )
#             return Response(
#                 {"message": "An unkown error occurred"},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )

#         cluster.locations.add(*system_location)
#         cluster.managers.add(*managers)
#         cluster.save()

#         serializer = self.serializer_class(cluster)
#         return Response(serializer.data, status=status.HTTP_201_CREATED)


# class ClusterAPI(views.APIView):

#     permission_classes = [permissions.IsTokenAuthenticated]
#     serializer_class = serializers.ClusterSerializer

#     def get(self, request, *args, **kwargs):

#         org_uuid = request.headers.get("organization-uuid")
#         org = fetch_data.get_organization(request.user, org_uuid)
#         member = fetch_data.get_member(request.user, org.uuid)

#         if fetch_data.is_admin_or_hr(member) is False:
#             return read_data.get_403_response()

#         cluster_uuid = self.kwargs.get("uuid")
#         cluster = get_cluster(org.uuid, cluster_uuid)
#         if cluster is None:
#             return read_data.get_404_response("Cluster")

#         serializer = self.serializer_class(cluster)
#         return Response(
#             serializer.data,
#             status=status.HTTP_200_OK,
#         )

#     def put(self, request, *args, **kwargs):

#         org_uuid = request.headers.get("organization-uuid")
#         org = fetch_data.get_organization(request.user, org_uuid)
#         member = fetch_data.get_member(request.user, org.uuid)

#         cluster_uuid = self.kwargs.get("uuid")
#         cluster = get_cluster(org.uuid, cluster_uuid)
#         if cluster is None:
#             return read_data.get_404_response("Cluster")

#         all_managers = cluster.managers.all()

#         is_admin_or_hr = fetch_data.is_admin_or_hr(member)
#         if is_admin_or_hr is False and all_managers.filter(uuid=member.uuid).exists() is False:
#             return read_data.get_403_response()

#         # if is_admin is False or is_admin is False and all_managers.filter(uuid=member.uuid).exists() is False:
#         #     return read_data.get_403_response()

#         name = request.data.get("name")
#         description = request.data.get("description")
#         location_uuids = request.data.get("location_uuids", [])
#         manager_uuids = request.data.get("manager_uuids", [])
#         cluster_status = request.data.get("status")

#         if cluster_status not in ("active", "inactive"):
#             return HTTP_400({}, {"message": "Cluster status must be active/inactive."})

#         if not name:
#             return HTTP_400({}, {"message": "Name is required."})

#         if not location_uuids:
#             return HTTP_400({}, {"message": "Location is required."})

#         if not manager_uuids:
#             return HTTP_400({}, {"message": "Manager is required."})

#         cluster.name = name
#         cluster.description = description
#         cluster.status = cluster_status

#         # * Location
#         try:
#             system_location = SystemLocation.objects.filter(
#                 Q(organization=org) & Q(uuid__in=location_uuids)
#             )
#             is_selected_system_loction = system_location.exists()
#         except (ValidationError) as err:
#             logger.error(err)
#             return Response(
#                 {"message": "Enter valid UUID(s)"}, status=status.HTTP_400_BAD_REQUEST
#             )


#         # exclude_loc_ids = []
#         # for location in system_location:
#         #     if location.cluster.exists():
#         #         loc_cluster =  location.cluster.all().first()
#         #         if loc_cluster is not None and loc_cluster != cluster:
#         #             exclude_loc_ids.append(location.id)

#         # if exclude_loc_ids:
#         #     system_location = system_location.exclude(id__in=exclude_loc_ids)

#         if is_selected_system_loction and system_location.exists() is False:
#             return HTTP_400({}, {"message": "Selected system location are inactive."})
#         if not system_location.exists():
#             return read_data.get_404_response("System Location(s)")

#         # * Manager
#         try:
#             managers = Member.objects.filter(
#                 Q(organization=org) & Q(uuid__in=manager_uuids)
#             )
#             is_selected_manager = managers.exists()
#         except (ValidationError) as err:
#             logger.error(err)
#             return Response(
#                 {"message": "Enter valid UUID(s)"}, status=status.HTTP_400_BAD_REQUEST
#             )

#         # exclude_manager_ids = []
#         # for manager in managers:
#         #     manager_cluster = manager.clusters.all().first()
#         #     if manager_cluster is not None and manager_cluster != cluster:
#         #         exclude_manager_ids.append(manager.id)

#         # if exclude_manager_ids:
#         #     managers = managers.exclude(id__in=exclude_manager_ids)

#         if is_selected_manager and not managers.exists():
#             return HTTP_400({}, {"message": "Selected managers are inactive."})
#         if not managers.exists():
#             return read_data.get_404_response("Member(s)")

#         # if Cluster.objects.filter(organization=org, name=name).exists():
#         #     return read_data.get_409_response("Cluster", "name")

#         try:
#             cluster.locations.clear()
#             cluster.managers.clear()

#             cluster.locations.add(*system_location)
#             cluster.managers.add(*managers)
#             cluster.save()
#         except IntegrityError as e:
#             logger.error(e)
#             return read_data.get_409_response("Cluster", "name")
#         except Exception as e:
#             logger.error(e)
#             logger.exception(f"Add exception for {e.__class__.__name__} in ClusterAPI")
#             return Response(
#                 {"message": "Unknown error occurred"},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )

#         serializer = self.serializer_class(cluster)

#         return Response(
#             serializer.data,
#             status=status.HTTP_200_OK,
#         )

#     def delete(self, request, *args, **kwargs):

#         org_uuid = request.headers.get("organization-uuid")
#         org = fetch_data.get_organization(request.user, org_uuid)
#         member = fetch_data.get_member(request.user, org.uuid)

#         if fetch_data.is_admin_or_hr(member) is False:
#             return read_data.get_403_response()

#         cluster_uuid = self.kwargs.get("uuid")
#         cluster = get_cluster(org.uuid, cluster_uuid)
#         if cluster is None:
#             return read_data.get_404_response("Cluster")

#         if fetch_data.is_admin(member) is False:
#             return read_data.get_403_response()

#         cluster.delete()
#         return read_data.get_200_delete_response("Cluster")


# class ClusterLocationsAPI(views.APIView):

#     permission_classes = [permissions.IsTokenAuthenticated]

#     def get(self, request, *args, **kwargs):

#         org_uuid = request.headers.get("organization-uuid")
#         org = fetch_data.get_organization(request.user, org_uuid)
#         member = fetch_data.get_member(request.user, org.uuid)

#         cluster_uuid = self.kwargs.get("uuid")
#         cluster = get_cluster(cluster_uuid)
#         if cluster is None:
#             return read_data.get_404_response("Cluster")

#         serializer = self.serializer_class(cluster)
#         return Response(
#             serializer.data,
#             status=status.HTTP_200_OK,
#         )

#     def post(self, request, *args, **kwargs):

#         org_uuid = request.headers.get("organization-uuid")
#         org = fetch_data.get_organization(request.user, org_uuid)
#         member = fetch_data.get_member(request.user, org.uuid)

#         cluster_uuid = self.kwargs.get("uuid")
#         cluster = get_cluster(cluster_uuid)
#         if cluster is None:
#             return read_data.get_404_response("Cluster")

#         if fetch_data.is_admin(member) is False or cluster.manager != member:
#             return read_data.get_403_response()

#         location_uuids = request.data.getlist("location_uuids")
#         try:
#             locations = Location.objects.filter(
#                 Q(organization=org) & Q(uuid__in=location_uuids)
#             )
#         except (ValidationError) as e:
#             logger.error(e)
#             return Response(
#                 {"message": "Enter valid UUID(s)"}, status=status.HTTP_400_BAD_REQUEST
#             )

#         if not locations.exists():
#             return read_data.get_404_response("Location(s)")

#         for location in locations:
#             # ? Does this mean location can belong to only one cluster?
#             if location.clusters.exists():
#                 continue
#             cluster.locations.add(location)

#         cluster.save()
#         serializer = self.serializer_class(cluster)
#         return Response(
#             serializer.data,
#             status=status.HTTP_200_OK,
#         )

#     def delete(self, request, *args, **kwargs):

#         org_uuid = request.headers.get("organization-uuid")
#         org = fetch_data.get_organization(request.user, org_uuid)
#         member = fetch_data.get_member(request.user, org.uuid)

#         cluster_uuid = self.kwargs.get("uuid")
#         cluster = get_cluster(cluster_uuid)
#         if cluster is None:
#             return read_data.get_404_response("Cluster")

#         if fetch_data.is_admin(member) is False or cluster.manager != member:
#             return read_data.get_403_response()

#         location_uuids = request.data.getlist("location_uuids", [])
#         try:
#             locations = Location.objects.filter(
#                 Q(organization=org) & Q(uuid__in=location_uuids)
#             )
#         except (ValidationError) as e:
#             logger.error(e)
#             return Response(
#                 {"message": "Enter valid UUID"}, status=status.HTTP_400_BAD_REQUEST
#             )

#         if not locations.exists():
#             return read_data.get_404_response("Location(s)")

#         for location in locations:
#             cluster.locations.remove(location)

#         cluster.save()
#         serializer = self.serializer_class(cluster)
#         return Response(
#             serializer.data,
#             status=status.HTTP_200_OK,
#         )


# class ClusterManagersAPI(views.APIView):

#     permission_classes = [permissions.IsTokenAuthenticated]

#     def get(self, request, *args, **kwargs):

#         org_uuid = request.headers.get("organization-uuid")
#         org = fetch_data.get_organization(request.user, org_uuid)
#         member = fetch_data.get_member(request.user, org.uuid)

#         cluster_uuid = self.kwargs.get("uuid")
#         cluster = get_cluster(cluster_uuid)
#         if cluster is None:
#             return read_data.get_404_response("Cluster")

#         serializer = self.serializer_class(cluster)
#         return Response(
#             serializer.data,
#             status=status.HTTP_200_OK,
#         )

#     def post(self, request, *args, **kwargs):

#         org_uuid = request.headers.get("organization-uuid")
#         org = fetch_data.get_organization(request.user, org_uuid)
#         member = fetch_data.get_member(request.user, org.uuid)

#         cluster_uuid = self.kwargs.get("uuid")
#         cluster = get_cluster(cluster_uuid)
#         if cluster is None:
#             return read_data.get_404_response("Cluster")

#         if fetch_data.is_admin(member) is False:
#             return read_data.get_403_response()

#         manager_uuids = request.data.get("manager_uuids", [])
#         try:
#             managers = Member.objects.filter(
#                 Q(organization=org) & Q(uuid__in=manager_uuids)
#             )
#         except (ValidationError) as e:
#             logger.error(e)
#             return Response(
#                 {"message": "Enter valid UUID(s)"}, status=status.HTTP_400_BAD_REQUEST
#             )

#         if not managers.exists():
#             return read_data.get_404_response("Member(s)")

#         for manager in managers:
#             cluster.managers.add(manager)
#         cluster.save()

#         serializer = self.serializer_class(cluster)
#         return Response(
#             serializer.data,
#             status=status.HTTP_200_OK,
#         )

#     def delete(self, request, *args, **kwargs):

#         org_uuid = request.headers.get("organization-uuid")
#         org = fetch_data.get_organization(request.user, org_uuid)
#         member = fetch_data.get_member(request.user, org.uuid)

#         cluster_uuid = self.kwargs.get("uuid")
#         cluster = get_cluster(cluster_uuid)
#         if cluster is None:
#             return read_data.get_404_response("Cluster")

#         if fetch_data.is_admin(member) is False:
#             return read_data.get_403_response()

#         manager_uuids = request.data.get("manager_uuids", [])
#         try:
#             managers = Member.objects.filter(
#                 Q(organization=org) & Q(uuid__in=manager_uuids)
#             )
#         except (ValidationError) as e:
#             logger.error(e)
#             return Response(
#                 {"message": "Enter valid UUID(s)"}, status=status.HTTP_400_BAD_REQUEST
#             )

#         if not managers.exists():
#             return read_data.get_404_response("Member(s)")

#         for manager in managers:
#             cluster.managers.add(manager)
#         cluster.save()

#         serializer = self.serializer_class(cluster)
#         return Response(
#             serializer.data,
#             status=status.HTTP_200_OK,
#         )




# class ClusterUploadAPI(views.APIView):

#     permission_classes = [permissions.IsTokenAuthenticated]

#     def get(self, request, *args, **kwargs):
#         org_uuid = request.headers.get("organization-uuid")
#         org = fetch_data.get_organization(request.user, org_uuid)
#         member = fetch_data.get_member(request.user, org.uuid)

#         if fetch_data.is_admin(member) is False:
#             return read_data.get_403_response()

#         schema = [
#             {
#                 "name": "Cluster Name",
#                 "description": "Cluster description",
#                 "system locations": "bangalore; indiranagar",
#                 "managers": "shahin.salim@peerxp.com; Manoj@gmail.com",
#                 "status": "active"
#             },
#             {
#                 "name": "Sample",
#                 "description": "Cluster description",
#                 "system locations": "Hsr; gurgaon",
#                 "managers": "shahin.salim@peerxp.com; Manoj@gmail.com",
#                 "status": "inactive"
#             },
#         ]
#         return HTTP_200(schema)
    

#     def post(self, request, *args, **kwargs):

#         org_uuid = request.headers.get('organization-uuid')
#         org = fetch_data.get_organization(request.user, org_uuid)
#         member = fetch_data.get_member(request.user, org.uuid)

#         if fetch_data.is_admin(member) is False:
#             return read_data.get_403_response()

#         csv_file = request.data.get("csv_file")
#         df = create_data.create_pandas_dataframe(csv_file)

#         member_role = fetch_data.get_member_role()
#         all_system_locations = SystemLocation.objects.filter(organization=org)
#         all_managers = Member.objects.filter(organization=org)
#         all_cluster = Cluster.objects.filter(organization=org)

#         failed_clusters = []
#         failed_rows = []
#         row_count = 1
#         created_clusters = 0
#         updated_count = 0


#         for row in df.values:
#             row_count += 1
#             is_update = 0
#             row_length = len(row)
#             print(row_length)


#             if row_length == 6:
#                 is_update = 1



#             try:

#                 name = row[0 + is_update]
#                 description = row[1 + is_update]
#                 locations = row[2 + is_update]
#                 managers = row[3 + is_update]
#                 cluster_status = row[4 + is_update]

#                 if row_length not in (6, 5):
#                     raise ValidationError("Row length must be 5 or 6.")

#                 if cluster_status not in ("active", "inactive"):
#                     raise ValidationError("Cluster status must be active/inactive.")

#                 if row_length == 5: # import
#                     name = str(name).strip()
#                     if not name:
#                         raise ValidationError("Cluster name is required")

#                     try:
#                         cluster = all_cluster.get(name=name)
#                     except Cluster.DoesNotExist:

#                         description =  str(description).strip()

#                         print(locations, "## locations")
#                         print(type(locations))
#                         if not locations:
#                             raise ValidationError("System Location are required.")

#                         list_of_locations = locations.split(";")
#                         locations = [str(loc).strip() for loc in list_of_locations]
#                         print(locations)

#                         if not locations:
#                             raise ValidationError("System Location are required.")


#                         # System locations
#                         system_locations = all_system_locations.filter(name__in=locations)
#                         print(system_locations)

#                         sys_location_ids = []

#                         # * Is System Locations part of another Cluster
#                         for location in system_locations:
#                             # if location.cluster.exists():
#                             #     continue
#                             sys_location_ids.append(location.id)

#                         if not sys_location_ids:
#                             raise ValidationError("System Location are required.")

#                         manger_names = managers
#                         list_of_managers = manger_names.split(";")
#                         managers = [str(loc).strip() for loc in list_of_managers]
#                         print(managers, "444444444444444444444444444444444444444444444444")
#                         managers = all_managers.filter(Q(user__email__in=managers)|Q(user__phone__in=managers))
#                         print(managers, "+++++++++++++++++++++++++++++++")

#                         manager_ids = []
#                         for manager in managers:
#                             # if manager.clusters.exists():
#                             #     continue
#                             manager_ids.append(manager.id)

#                         print(manager_ids, "@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@")

#                         if not manager_ids:
#                             raise ValidationError("Manager are required.")

#                         cluster_obj = Cluster.objects.create(
#                             name=name, description=description, organization=org, status=cluster_status
#                         )

#                         cluster_obj.locations.add(*sys_location_ids)
#                         cluster_obj.managers.add(*manager_ids)
#                         cluster_obj.save()

#                         created_clusters += 1
#                         continue

#                 if row_length == 6: # Update

#                     if not row[0]:
#                         raise ValidationError("uuid is required")

#                     cluster = all_cluster.filter(uuid=row[0]).get()
#                     is_update = 1

#                     if row[1]:
#                         cluster.name = row[1]

#                 print("!!!!!!!!!!!!"*10)

#                 manger_names = managers
#                 if description in ("", "NA"):
#                     cluster.description = None
#                 else:
#                     cluster.description = row[1 + is_update]

#                 print(locations)
#                 if not locations:
#                     raise ValidationError("System Location are required.")

#                 list_of_locations = locations.split(";")
#                 locations = [str(loc).strip() for loc in list_of_locations]

#                 print(locations)

#                 if not locations:
#                     raise ValidationError("System Location are required.")

#                 system_locations = all_system_locations.filter(name__in=locations)

#                 print(system_locations)
#                 print(cluster.locations.all())

#                 system_loc_ids = []
#                 for location in system_locations:
#                     # if location.cluster.exists() and cluster.locations.filter(uuid=location.uuid).exists() is False:
#                     #     continue
#                     system_loc_ids.append(location.id)

#                 if not system_loc_ids:
#                     raise ValidationError("System Location are required.")

#                 manger_names = row[3 + is_update]
#                 list_of_managers = manger_names.split(";")
#                 managers = [str(loc).strip() for loc in list_of_managers]
#                 print(manger_names, "%%%%%%%%%%%%%%%%%%%%%%%%%%55")
#                 managers = all_managers.filter(Q(user__email__in=managers)|Q(user__phone__in=managers))

#                 print(managers, "!!!!!!!!!!!!!!!!!!!!! Mn")

#                 manager_ids = []
#                 for manager in managers:
#                     # if manager.clusters.exists() and cluster.managers.filter(uuid=manager.uuid).exists() is False:
#                     #     continue
#                     manager_ids.append(manager.id)
#                 print(manager_ids, "@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@")
#                 if not manager_ids:
#                     raise ValidationError("Manager are required.")

#                 cluster.locations.add(*system_loc_ids)
#                 cluster.managers.add(*manager_ids)
#                 cluster.status = cluster_status
#                 cluster.save()
#                 updated_count += 1

#             except Exception as err:
#                 failed_rows.append(row_count)
#                 failed_clusters.append(
#                     {
#                         "reason": str(err.__class__.__name__),
#                         "detailed_reason": str(err),
#                     }
#                 )

#                 # try:
#                 #     failed_clusters.append(
#                 #         {
#                 #             "reason": str(err.__class__.__name__),
#                 #             "detailed_reason": str(err),
#                 #         }
#                 #     )
#                 # except Exception as err2:
#                 #     pass
#                 # logger.error(err2)
#                 # logger.exception(
#                 #     f"Add exception for {err2.__class__.__name__} in DepartmentUploadCSVAPI"
#                 # )


#         return Response(
#             {
#                 "failed_clusters": failed_clusters,
#                 "created_count": created_clusters,
#                 "failed_rows": failed_rows,
#                 "updated_count": updated_count

#             },
#             status=status.HTTP_201_CREATED
#         )
