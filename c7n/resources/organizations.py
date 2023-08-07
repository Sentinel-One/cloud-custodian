import boto3

from c7n.filters import Filter
from c7n.manager import resources
from c7n import query
from c7n.query import DescribeSource
from c7n.utils import (
    local_session, type_schema
)

POLICY_ID = 'Id'


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
        policy_id = resource['Id']
        policies = client.describe_policy(PolicyId=policy_id)
        if len(policies) > 0 and policies['Policy'] is not None:
            return (policies['Policy'])['Content']

    def process(self, resources, event=None):
        c = local_session(self.manager.session_factory).client('organizations')
        value = self.data.get('value', True)
        if not value:
            return resources
        result = []
        for r in resources:
            content = self._include_policies(c, r)
            r['Content'] = content
            result.append(r)
        return result


class DescribeAccount(DescribeSource):

    def resources(self, query=None):
        client = boto3.client('organizations')
        b = client.can_paginate("list_accounts")
        val = super(DescribeAccount, self).resources(query=query)
        return val


@resources.register('org-account')
class OrgAccounts(query.QueryResourceManager):
    class resource_type(query.TypeInfo):
        service = 'organizations'
        id = 'AccountId'
        name = 'AccountName'
        enum_spec = ('list_accounts', 'Accounts', None)
        cfn_type = config_type = "AWS::Organizations::Accounts"
        # Denotes this resource type exists across regions
        global_resource = True
        arn = 'Arn'

    source_mapping = {
        'describe': DescribeAccount,
        'config': query.ConfigSource
    }


@OrgAccounts.filter_registry.register('include-parent-hierarchy')
class IncludeParentHierarchyFilter(Filter):
    schema = type_schema('include-parent-hierarchy', value={'type': 'boolean'})
    permissions = ('org:list_parents',)

    def get_parent_ids(self, parent_hierarchy):
        parent_ids = set()
        for parent in parent_hierarchy:
            parent_ids.add(parent['Id'])
        return parent_ids

    def _get_parent_hierarchy(self, client, resource):
        child_id = resource['Id']
        has_parent = True
        parents = []
        while has_parent:
            parent = client.list_parents(ChildId=child_id)
            if len(parent) > 0 and parent['Parents'] is not None:
                parent = parent['Parents'][0]
                parents.append(parent)
                if parent['Type'] == 'ROOT':
                    has_parent = False
            child_id = parent['Id']
        return parents

    def process(self, resources, event=None):
        c = local_session(self.manager.session_factory).client('organizations')
        value = self.data.get('value', True)
        if not value:
            return resources
        result = []
        for r in resources:
            parent_hierarchy = self._get_parent_hierarchy(c, r)
            parent_ids = self.get_parent_ids(parent_hierarchy)
            r['parents'] = list(parent_ids)
            result.append(r)
        return result


@OrgAccounts.filter_registry.register('include-attached-policy')
class IncludeAttachedPolicyFilter(Filter):
    schema = type_schema('include-attached-policy', value={'type': 'boolean'})
    permissions = ('org:list_policies_for_target',)

    def _get_attached_policy(self, client, resource):
        result = client.list_policies_for_target(TargetId=resource['Id'], Filter='SERVICE_CONTROL_POLICY')
        if len(result['Policies']) > 0 and result['Policies'] is not None:
            return result['Policies']

    def get_attached_policy_arns(self, policies) -> set:
        policy_arns = set()
        for policy in policies:
            policy_arns.add(policy[POLICY_ID])
        return policy_arns

    def process(self, resources, event=None):
        c = local_session(self.manager.session_factory).client('organizations')
        value = self.data.get('value', True)
        if not value:
            return resources
        result = []
        for r in resources:
            policies = self._get_attached_policy(c, r)
            if len(policies) > 0 and policies is not None:
                r['attached-policies'] = list(self.get_attached_policy_arns(policies))
            result.append(r)
        return result


@OrgAccounts.filter_registry.register('include-inherited-policy')
class IncludeInheritedPolicyFilter(Filter):
    schema = type_schema('include-inherited-policy', value={'type': 'boolean'})
    permissions = ('org:list_policies_for_target',)

    def get_all_inherited_policies(self, client, target_ids='set') -> dict:
        policy_dictionary = dict()
        for target_id in target_ids:
            result = client.list_policies_for_target(TargetId=target_id, Filter='SERVICE_CONTROL_POLICY')
            policies = result['Policies']
            if len(policies) > 0 and policies is not None:
                policy_dictionary[target_id] = policies
        return policy_dictionary

    def process(self, resources, event=None):
        c = local_session(self.manager.session_factory).client('organizations')
        value = self.data.get('value', True)
        if not value:
            return resources
        parent_ids = self.get_all_parents_ids(resources)
        policy_dictionary = self.get_all_inherited_policies(c, target_ids=parent_ids)
        result = []
        for r in resources:
            inherited_policy_arns = self.get_all_inherited_policy_arns(r, policy_dictionary)
            r['inherited_parent_policies'] = list(inherited_policy_arns)
            result.append(r)
        return result

    def get_all_parents_ids(self, resources) -> set:
        parent_ids = set()
        for r in resources:
            parent_ids.update(r['parents'])
        return parent_ids

    def get_all_inherited_policy_arns(self, r, policy_dictionary='dict') -> set:
        inherited_policy_arns = set()
        for parent in r['parents']:
            policies = policy_dictionary[parent]
            if len(policies) > 0 and policies is not None:
                for policy in policies:
                    inherited_policy_arns.add(policy[POLICY_ID])
        return inherited_policy_arns


@resources.register('org-unit')
class OrganizationalUnits(query.QueryResourceManager):
    class resource_type(query.TypeInfo):
        service = 'organizations'
        enum_spec = ('list_roots', 'Roots', None)
        cfn_type = config_type = "AWS::Organizations::Roots"
        global_resource = True
        arn = 'Arn'

    source_mapping = {
        'config': query.ConfigSource
    }


@OrganizationalUnits.filter_registry.register('include-all-children')
class IncludeAllChildFilter(Filter):
    schema = type_schema('include-all-children', value={'type': 'boolean'})

    permissions = ('org:list_organizational_units_for_parent',)

    def get_organizational_units_for_parent(self, client, parent_id):
        result = client.list_organizational_units_for_parent(ParentId=parent_id)
        return result['OrganizationalUnits']

    def process(self, output, event=None):
        c = local_session(self.manager.session_factory).client('organizations')
        value = self.data.get('value', True)
        if not value:
            return output
        result = []
        for r in output:
            organization_units = self.get_organizational_units_for_parent(c, r['Id'])
            self.add_ou_to_result(organization_units, r)
            self.get_ou_hierarchy(c,organization_units, result)
            result.append(r)
        return result

    def get_ou_hierarchy(self,client, organization_units, result):
        for organization_unit in organization_units:
            result.append(organization_unit)
            new_organization_units = self.get_organizational_units_for_parent(client,organization_unit['Id'])
            self.add_ou_to_result(new_organization_units, organization_unit)
            if len(new_organization_units) > 0 and new_organization_units is not None:
                self.get_ou_hierarchy(client, new_organization_units, result)

    def add_ou_to_result(self, organization_units, r):
        children = set()
        if len(organization_units) > 0 and organization_units is not None:
            for ou in organization_units:
                children.add(ou['Id'])
            r['child_organization_units'] = list(children)
        return children


@OrganizationalUnits.filter_registry.register('include-all-account')
class IncludeAllAccountsFilter(Filter):
    schema = type_schema('include-all-account', value={'type': 'boolean'})

    permissions = ('org:list_accounts_for_parent',)

    def get_accounts(self, client, resource):
        result = client.list_accounts_for_parent(ParentId=resource['Id'])
        return result['Accounts']

    def process(self, output, event=None):
        c = local_session(self.manager.session_factory).client('organizations')
        value = self.data.get('value', True)
        if not value:
            return output
        result = []
        for r in output:
            accounts = self.get_accounts(c, r)
            if len(accounts) > 0 and accounts is not None:
                children = set()
                for account in accounts:
                    children.add(account['Id'])
                r['child_accounts'] = list(children)
            result.append(r)
        return result


@OrganizationalUnits.filter_registry.register('include-attached-policy')
class IncludeAttachedSCPPolicyFilter(Filter):
    schema = type_schema('include-attached-policy', value={'type': 'boolean'})

    permissions = ('org:list_accounts_for_parent',)

    def get_attached_scp_policy(self, client, resource):
        result = client.list_policies_for_target(TargetId=resource['Id'], Filter='SERVICE_CONTROL_POLICY')
        return result['Policies']

    def process(self, output, event=None):
        c = local_session(self.manager.session_factory).client('organizations')
        value = self.data.get('value', True)
        if not value:
            return output
        result = []
        for r in output:
            policies = self.get_attached_scp_policy(c, r)
            if len(policies) > 0 and policies is not None:
                policy_arns = set()
                for policy in policies:
                    policy_arns.add(policy[POLICY_ID])
                r['attached-policies'] = list(policy_arns)
            result.append(r)
        return result
