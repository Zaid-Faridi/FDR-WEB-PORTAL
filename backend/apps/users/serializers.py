from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.exceptions import AuthenticationFailed
from django.contrib.auth import get_user_model
from apps.institutions.serializers import InstitutionSerializer
from apps.common.audit import record_audit_event

User = get_user_model()


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = user.role
        token['username'] = user.username
        token['institution_id'] = user.institution_id
        if user.institution:
            token['institution_name'] = user.institution.name
            token['aicte_id'] = user.institution.aicte_id
        return token

    def validate(self, attrs):
        request = self.context.get('request')
        ip_address = None
        user_agent = ''
        if request:
            xf = request.META.get('HTTP_X_FORWARDED_FOR')
            ip_address = xf.split(',')[0].strip() if xf else request.META.get('REMOTE_ADDR')
            user_agent = request.META.get('HTTP_USER_AGENT', '')

        username = attrs.get('username')
        user = User.objects.filter(username=username).first()

        # 1. Pre-auth check: Account Lockout
        if user and user.is_locked_out():
            record_audit_event(
                action='LOGIN_BLOCKED_LOCKOUT',
                entity_type='User',
                entity_id=str(user.id),
                actor=user,
                actor_username=user.username,
                actor_role=user.role,
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={'locked_until': user.locked_until.isoformat() if user.locked_until else None}
            )
            raise AuthenticationFailed(
                f"Account is locked due to excessive failed attempts. Please try again after {user.locked_until}."
            )

        # 2. Authenticate credentials
        try:
            data = super().validate(attrs)
        except (AuthenticationFailed, Exception) as exc:
            if user:
                is_now_locked = user.record_failed_login(ip_address)
                if is_now_locked:
                    record_audit_event(
                        action='ACCOUNT_LOCKOUT',
                        entity_type='User',
                        entity_id=str(user.id),
                        actor=user,
                        actor_username=user.username,
                        actor_role=user.role,
                        ip_address=ip_address,
                        user_agent=user_agent,
                        metadata={'failed_attempts': user.failed_login_attempts}
                    )
                    raise AuthenticationFailed(
                        "Account has been locked for 15 minutes due to 5 consecutive failed login attempts."
                    )
                else:
                    record_audit_event(
                        action='LOGIN_FAILURE',
                        entity_type='User',
                        entity_id=str(user.id),
                        actor=user,
                        actor_username=user.username,
                        actor_role=user.role,
                        ip_address=ip_address,
                        user_agent=user_agent,
                        metadata={'failed_attempts': user.failed_login_attempts}
                    )
            else:
                record_audit_event(
                    action='LOGIN_FAILURE_UNKNOWN_USER',
                    entity_type='Auth',
                    entity_id=username or 'unknown',
                    actor_username=username or 'unknown',
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
            raise exc

        # 3. Successful password check: reset failed attempts counter
        self.user.reset_failed_logins()

        # 4. Optional TOTP 2FA Verification for Officers / Approvers
        otp_code = self.initial_data.get('otp_code') or self.initial_data.get('totp_code')
        if self.user.totp_enabled:
            if not otp_code:
                # Prompt client for 2FA code
                return {
                    'requires_2fa': True,
                    'username': self.user.username,
                    'message': 'Two-factor authentication code (TOTP) is required for this account.',
                }
            if not self.user.verify_totp(otp_code):
                record_audit_event(
                    action='LOGIN_FAILURE_INVALID_2FA',
                    entity_type='User',
                    entity_id=str(self.user.id),
                    actor=self.user,
                    actor_username=self.user.username,
                    actor_role=self.user.role,
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
                raise AuthenticationFailed("Invalid or expired TOTP 2FA verification code.")

        # 5. Record Login Success
        record_audit_event(
            action='LOGIN_SUCCESS',
            entity_type='User',
            entity_id=str(self.user.id),
            actor=self.user,
            actor_username=self.user.username,
            actor_role=self.user.role,
            ip_address=ip_address,
            user_agent=user_agent,
            new_state={'role': self.user.role, 'institution_id': self.user.institution_id}
        )

        data['user'] = {
            'id': self.user.id,
            'username': self.user.username,
            'email': self.user.email,
            'role': self.user.role,
            'totp_enabled': self.user.totp_enabled,
            'institution_id': self.user.institution_id,
            'institution_name': self.user.institution.name if self.user.institution else None,
            'aicte_id': self.user.institution.aicte_id if self.user.institution else None,
        }
        return data


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'role',
            'institution',
            'phone',
            'designation',
            'is_active',
            'password',
            'date_joined',
        ]
        read_only_fields = ['id', 'date_joined']

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = super().create(validated_data)
        if password:
            user.set_password(password)
            user.save()
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    institution = InstitutionSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'role',
            'institution',
            'phone',
            'designation',
        ]
        read_only_fields = fields
