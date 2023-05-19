@Library("jenkins-libs") _

k8s.jnlpDinD { label -> node(label) {

    stage("Checkout") {
        checkout scm
        // pre-commit will fail if the workspace is not
        // a safe directory
        sh "git config --global --add safe.directory ${env.WORKSPACE}"
        // allow write from the container
        sh "chmod -R a+rwX ${env.WORKSPACE}"
    }

    stage("Build") {
        docker.image("quay.io/quarck/python:3").inside {
            sh "make build"
        }
    }

}}