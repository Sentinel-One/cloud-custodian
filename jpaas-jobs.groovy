folder('builds/cloud-custodian-libraries') {
    displayName('cloud-custodian-libraries')
    description('cloud-custodian-libraries build folder')
}

folder('builds/cloud-custodian-libraries/cloud-custodian') {
    displayName('cloud-custodian')
    description('cloud-custodian library build folder')
}

pipelineJob('builds/cloud-custodian-libraries/cloud-custodian/release-library') {

    definition {
        cpsScm {
            scm {
                git {
                    remote {
                        url('git@github.com:Sentinel-One/cloud-custodian.git')
                        credentials(jpaasGithubUserSshKey)
                    }
                    branch('${BRANCH}')
                }
            }
            scriptPath('jenkins-jobs/release-pipeline.groovy')
        }
    }
    authorization {
        permissions('linux_agent_team', [
            'hudson.model.Item.Cancel',
            'hudson.model.Item.Read',
            'hudson.model.Item.Build',
            'hudson.model.Run.Replay',
            'hudson.model.Item.Configure'
        ])
         permissions('embedded-devops', [
             'hudson.model.Item.Cancel',
             'hudson.model.Item.Read',
             'hudson.model.Item.Build',
             'hudson.model.Run.Replay',
             'hudson.model.Item.Configure'
        ])
        permissions('cloud_ops_team', [
             'hudson.model.Item.Cancel',
             'hudson.model.Item.Read',
             'hudson.model.Item.Build',
             'hudson.model.Run.Replay',
             'hudson.model.Item.Configure'
        ])
    }
    properties {
        durabilityHint { hint('PERFORMANCE_OPTIMIZED') }
    }
    logRotator {
        numToKeep(100)
        daysToKeep(30)
    }
    parameters {
        choiceParam("VERSION_BUMP", ["minor", "patch", "major", "prerelease"], "Bump specific version part, see semver2.")
        gitParameter {
            name('BRANCH')
            type('PT_BRANCH')
            defaultValue('origin/main')
            branch('')
            description('Choose git branch to build from')
            branchFilter('(.*)')
            tagFilter('*')
            sortMode('DESCENDING_SMART')
            selectedValue('DEFAULT')
            quickFilterEnabled(true)
            listSize('10')
            useRepository('')
        }
    }
    configure { project ->
        def scriptContainers = project / 'properties' / 'hudson.model.ParametersDefinitionProperty' / 'parameterDefinitions'
        scriptContainers.each { org_level ->
            // wrap <script> inside a <secureScript>
            def script_level = org_level / 'script'
            script_level.appendNode('secureScript', [plugin: 'script-security@']).with {
                appendNode('sandbox', 'true')
                appendNode('script', script_level.script.text())
                script_level.remove(script_level / 'script')
            }
            script_level.appendNode('secureFallbackScript', [plugin: 'script-security@']).with {
                appendNode('sandbox', 'true')
                appendNode('script', script_level.fallbackScript.text())
                script_level.remove(script_level / 'fallbackScript')
            }
        }
    }
}

multibranchPipelineJob('builds/cloud-custodian-libraries/cloud-custodian/build-library') {
    branchSources {
        github {
            id('builds/cloud-custodian-libraries/cloud-custodian/build-library-cloud-custodian-c7n')
            repository('cloud-custodian')
            repoOwner('Sentinel-One')
            scanCredentialsId(jenkinsGitHubUserToken)
            // do not build fork heads
            buildForkPRHead(false)
            // do not build on fork merges, we do not support forks
            buildForkPRMerge(false)
            // do build origin (master)
            buildOriginBranch(true)
            // build origin branch that has opened PR
            buildOriginBranchWithPR(false)
            // do not build branches that were merged with base branch
            buildOriginPRMerge(false)
            // do not build on origin branches PRs
            buildOriginPRHead(true)

        }
    }
    factory {
        workflowBranchProjectFactory {
            scriptPath('jenkins-jobs/build-pipeline.groovy')
        }
    }
   authorization {
        permissions('linux_agent_team', [
            'hudson.model.Item.Cancel',
            'hudson.model.Item.Read',
            'hudson.model.Item.Build',
            'hudson.model.Run.Replay',
            'hudson.model.Item.Configure'
        ])
         permissions('embedded-devops', [
             'hudson.model.Item.Cancel',
             'hudson.model.Item.Read',
             'hudson.model.Item.Build',
             'hudson.model.Run.Replay',
             'hudson.model.Item.Configure'
        ])
        permissions('cloud_ops_team', [
             'hudson.model.Item.Cancel',
             'hudson.model.Item.Read',
             'hudson.model.Item.Build',
             'hudson.model.Run.Replay',
             'hudson.model.Item.Configure'
        ])
    }
    orphanedItemStrategy {
        discardOldItems {
            numToKeep(20)
            daysToKeep(20)
        }
    }
    triggers {
        periodicFolderTrigger {
            interval("1m")
        }
    }
}