from rest_framework.views import APIView
from rest_framework import status
from rest_framework.response import Response
from rest_framework import permissions

from django.shortcuts import get_object_or_404
from django.http.response import Http404
from django.utils import timezone

from events.models import PersonSession, Session, SessionCountSpecial
from core.models import Profile
from badges.models import PersonBadge

from events.serializers import PersonSessionSerializer, PersonSessionAttendSerializer
from core.serializers import ProfileSerializer
from badges.serializers import PersonBadgeGrantSerializer

class GetOrMarkSession(APIView):
    permission_classes = (permissions.IsAuthenticated,)
    
    def markAttendance(self, sessionId, user):
        """
        Marks the attendance of a user for a particular session
        """

        try:
            obj = get_object_or_404(PersonSession, user=user)
            obj.session.add(sessionId)

            serialized = PersonSessionAttendSerializer(obj)

            serializer = PersonSessionAttendSerializer(obj, data=serialized.data)
            if serializer.is_valid():
                serializer.save()
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Http404:
            data = {"user": user.id, "session": [sessionId]}
            serialized = PersonSessionAttendSerializer(data=data)

            if serialized.is_valid():
                serialized.save()
            else:
                return Response(serialized.errors, status=status.HTTP_400_BAD_REQUEST)


    def grantBadge(self, badgeId, user):
        """
        Checks if the person already has a particular badge.
        If not, then grants a new Badge

        returns True if new badge is called
        returns False if existing badge is called
        """

        earned = PersonBadge.objects.filter(user=user, badge__in=[badgeId])
        if len(earned)!=0:
            return False

        try:
            obj = get_object_or_404(PersonBadge, user=user)
            obj.badge.add(badgeId)

            serialized = PersonBadgeGrantSerializer(obj)

            serializer = PersonBadgeGrantSerializer(obj, data=serialized.data)
            if serializer.is_valid():
                serializer.save()
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Http404:
            data = {"user": user.id, "badge": [badgeId]}
            serialized = PersonBadgeGrantSerializer(data=data)

            if serialized.is_valid():
                serialized.save()
            else:
                return Response(serialized.errors, status=status.HTTP_400_BAD_REQUEST)

        return True

    def grantSessionCountBadge(self, user):
        """
        Checks if the person has attended a set number of sessions
        as set in "SessionCountSpecial" model and grants badge 
        accordingly.
        """

        personSessions = PersonSession.objects.filter(user=user).first()
        count = personSessions.session.count()
        
        eligibleBadges = SessionCountSpecial.objects.filter(count=count)

        if len(eligibleBadges) == 0:
            return False
        else:
            for item in eligibleBadges:
                badgeEarned = self.grantBadge(item.badge, user)
        return badgeEarned
        

    def get(self, request, format=None):
        """
        Return UUID and sessions array for a user.
        UUID can be used to display public profile.
        """

        user = request.user
        response_obj = {}

        try:
            data = get_object_or_404(PersonSession, user=user)
            personSessionSerialized = PersonSessionSerializer(data)
            response_obj['sessions'] = personSessionSerialized.data['sessions'] 
        except Http404:
            response_obj['sessions'] = []

        profile = Profile.objects.filter(user=user).first()
        profileSerialized = ProfileSerializer(profile)
        
        response_obj['uuid'] = profileSerialized.data['id']

        return Response(response_obj)


    def post(self, request):
        """
        Handles request for marking attendance in a session
        and grant badges accordingly. 
        Compatible with parallel sessions. 
        """

        user = request.user 
        track = request.data['track']
        now = timezone.localtime(timezone.now())
        newsession = Session.objects.filter(end__gte=now, start__lte=now, track=track).first()

        try:
            self.markAttendance(newsession.sessionId, user)
            badgeEarnedNew = self.grantBadge(newsession.badge, user)
            badgeEarnedSpecial = self.grantSessionCountBadge(user)
        
            response = {'user': user.email, 'success': True, 'badgeEarned': (badgeEarnedNew or badgeEarnedSpecial)}
            return Response(response, status=status.HTTP_201_CREATED)

        except:
            return Response({"error": "something went wrong"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GetPublicSessions(APIView):
    """
    Retrieve public profile with the UUID sent
    Obscures the email ID to prevent private info leak
    but yet verify if it's the correct person's profile
    """

    permission_classes = (permissions.AllowAny,)

    def get(self, request, uid, format=None):
        try:
            obj = get_object_or_404(Profile, pk=uid)

            data = get_object_or_404(PersonSession, user=obj.user)
            serializer = PersonSessionSerializer(data)

            response_obj = serializer.data
        
            email = obj.user.email
            split = email.split('@')
            joined = split[0][:3]+"*****@" + split[1]
            response_obj['email'] = joined
        
            return Response(response_obj)

        except Http404:
            return Response({'error': 'user does not exist'}, status=status.HTTP_404_NOT_FOUND)