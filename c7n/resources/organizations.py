from c7n.filters import Filter
import boto3
from c7n.manager import resources
from c7n import query
from c7n.query import DescribeSource
from c7n.utils import (
    local_session, type_schema
)

class DescribeSCP(DescribeSource):
    def resources(self, query=None):
        client = boto3.client('organizations')
        b = client.can_paginate("list_policies")
        val = super(DescribeSCP, self).resources(query=query)
        return val

@resources.register('org-scp')
class OrgPolicies(query.QueryResourceManager):

    class resource_type(query.TypeInfo):
                service = 'organizations'
                id = 'PolicyId'
                name = 'PolicyName'
                enum_spec = ('list_policies', 'Policies', None)
                cfn_type = config_type = "AWS::Organizations::Policies"
                # Denotes this resource type exists across regions
                global_resource = True
                arn = 'Arn'

    source_mapping = {
       'describe': DescribeSCP,
       'config': query.ConfigSource
    }

    def __init__(self, ctx, data):
        super(OrgPolicies, self).__init__(ctx, data)
        self.queries = self.data.get('query', [])

    def resources(self, query=None):
        query = query or {}
        query['Filter'] = 'SERVICE_CONTROL_POLICY'
        return super(OrgPolicies, self).resources(query=query)

@OrgPolicies.filter_registry.register('include-statements')
class IncludeOrganizationPolicyStatements(Filter):

    """Append policy statements
    True: Include policy statements
    False: Exclude policy statements

    :example:

    .. code-block:: yaml

        policies:
          - name: org-scp-with-statements
            resource: aws.org-scp
            filters:
              - type: include-statements
                value: True
    """

    schema = type_schema('include-statements', value={'type': 'boolean'})
    permissions = ('org:describePolicies',)

    def _include_policies(self, client, resource):
        policy_id = resource['Id'];
        policies = client.describe_policy(PolicyId=policy_id)
        if len(policies) > 0 and policies['Policy'] is not None:
            return (policies['Policy'])['Content']
    def process(self, resources, event=None):
        c = local_session(self.manager.session_factory).client('organizations')
        value = self.data.get('value', True)
        if value == False:
            return resources
        result = []
        for r in resources:
            content = self._include_policies(c, r)
            r['Content'] = content
            result.append(r)
        return result