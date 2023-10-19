@Library("jenkins-libs") _

import groovy.transform.Field

@Field slackChannelName = "s1-cloud-custodian-jenkins"
@Field pythonImageVersion = "3.10-buster"
@Field pythonImageName = "artifactory.eng.sentinelone.tech/docker-remote/python"
@Field artCredentialsId = "jpaas-artifactory-ha-credentials"
@Field artUrl = "https://artifactory.eng.sentinelone.tech"
@Field isRelease = false
@Field isPRBuild = false

@Field artVersion = "0.9.26.4.34"


timeout(activity: true, time: 10) {
    timestamps {
        ansiColor('xterm') {
            k8s.multiPod(
                    BASE_CONTAINER_REQUEST_MEMORY: "2Gi",
                    REQUEST_CPU: "4",
                    REQUEST_MEMORY: "4Gi") { label ->
                node(label) {
                    try {
                        def setuptoolsDevVersion

                        stage('Checkout') {
                            // so the checkout grabs the tags, the shorthand ( "checkout scm" ) doesn't fetches those ...
                            checkout([
                                    $class                           : 'GitSCM',
                                    branches                         : scm.branches,
                                    doGenerateSubmoduleConfigurations: false,
                                    extensions                       : [[
                                                                                $class             : 'SubmoduleOption',
                                                                                disableSubmodules  : false,
                                                                                parentCredentials  : true,
                                                                                recursiveSubmodules: true,
                                                                                reference          : '',
                                                                                trackingSubmodules : false
                                                                        ]],
                                    submoduleCfg                     : [],
                                    userRemoteConfigs                : scm.userRemoteConfigs
                            ])
                        }

                        stage("Prepare environment") {
                            def BRANCH_NAME = getCurrentBranch()
                            isRelease = BRANCH_NAME.startsWith("remotes/origin/release/")
                            isPRBuild = BRANCH_NAME.startsWith("PR-")

                            if (isPRBuild) {
                                say("This is a PR build, packages won't be published so they won't conflict with the branch builds.")
                            }
                            if (isRelease) {
                                say("This is a release build, packages won't be published so please run release job to publish the package.")
                            }

                            // Resolve versions
                            docker.withRegistry(artUrl, artCredentialsId) {
                                docker.image("${pythonImageName}:${pythonImageVersion}").inside {
                                    pip.withPipConfig() {
                                        sh('pip install setuptools_scm')
                                    }
                                    // Evaluated version without dev suffix- Need to fix
                                    // artVersion = sh(script: 'python -m setuptools_scm --strip-dev', returnStdout: true).trim()
                                    setuptoolsDevVersion = sh(script: 'python -m setuptools_scm', returnStdout: true).trim()
                                    say("artVersion: ${artVersion}")
                                }
                            }
                        }

                        stage('Compile and build python package') {
                            def artPythonVersion = artVersion
                            if (!isRelease) {
                                // In case of python version, we need to manually add the timestamp so the
                                // new artifactory is OK with it in case of rebuild. According on setuptools_scm
                                // this will make the version dirty, but it's a necessary hack
                                timestamp = sh(script: "date +\"%y%m%d%H%M\"", returnStdout: true).trim()
                                artPythonVersion = "${setuptoolsDevVersion}.dev${timestamp}"
                                say("not a release - version: ${artPythonVersion}")
                            }

                            docker.withRegistry(artUrl, artCredentialsId) {
                                // python
                                docker.image("${pythonImageName}:${pythonImageVersion}")
                                        .inside("-e SETUPTOOLS_SCM_PRETEND_VERSION=${artPythonVersion}") {
                                            pip.withPipConfig() {
                                                GString packageName = "s1-c7n-${artPythonVersion}-py3-none-any.whl"
                                                GString packagePath = "dist/${packageName}"
                                                sh("pip3 install build twine")
                                                sh("pip3 install poetry")
                                                sh("poetry install -v")
                                                sh("poetry install -v --all-extras")
                                                sh("pip3 install wheel")
                                                sh("poetry build --format wheel")
                                                sh("poetry build -v")
                                                sh("twine check --strict dist/*")
                                            }
                                        }
                            }
                        }
                    } catch (Exception ex) {
                        currentBuild.result = "FAILURE"
                        slackMe.notifyBuild(currentBuild.result, slackChannelName)
                        throw new Exception(ex)
                    } finally {
                        slackMe.notifyCustom(currentBuild.result, slackChannelName, "The build is successfully completed with a new release - version ${artVersion}")
                    }
                } // close node
            } // close slave
        } // close color
    } // close timestamp
} // close timeout

def getCurrentBranch () {
    return sh (
    script: 'git name-rev --name-only HEAD',
    returnStdout: true
    ).trim()
}