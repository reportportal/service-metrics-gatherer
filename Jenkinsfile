#!groovy

node {

    load "$JENKINS_HOME/jobvars.env"

    stage('Checkout') {
        checkout scm
    }

    docker.withServer("$DOCKER_HOST") {
        stage('Build Docker Image') {
            sh """
                            MAJOR_VER=\$(cat VERSION)
                            BUILD_VER="\${MAJOR_VER}-${env.BUILD_NUMBER}"
                            make build-image-dev v=\$BUILD_VER
                        """
        }
        stage('Deploy Container') {
            sh "docker-compose -f $COMPOSE_FILE_RP -p reportportal up -d --force-recreate metrics-gatherer"
            stage('Push to ECR') {
                withEnv(["AWS_URI=${AWS_URI}", "AWS_REGION=${AWS_REGION}"]) {
                    sh 'docker tag reportportal-dev/service-metrics-gatherer ${AWS_URI}/metrics-gatherer'
                    sh 'docker tag reportportal-dev/service-metrics-gatherer ${LOCAL_REGISTRY}/metrics-gatherer'
                    sh 'docker push ${LOCAL_REGISTRY}/metrics-gatherer'
                    def image = env.AWS_URI + '/metrics-gatherer'
                    def url = 'https://' + env.AWS_URI
                    def credentials = 'ecr:' + env.AWS_REGION + ':aws_credentials'
                    docker.withRegistry(url, credentials) {
                        docker.image(image).push('SNAPSHOT-${BUILD_NUMBER}')
                    }
                }
            }
        }
        
        stage('Cleanup') {
            docker.withServer("$DOCKER_HOST") {
                withEnv(["AWS_URI=${AWS_URI}", "LOCAL_REGISTRY=${LOCAL_REGISTRY}"]) {
                    sh 'docker rmi ${AWS_URI}/metrics-gatherer:SNAPSHOT-${BUILD_NUMBER}'
                    sh 'docker rmi ${AWS_URI}/metrics-gatherer:latest'
                    sh 'docker rmi ${LOCAL_REGISTRY}/metrics-gatherer:latest'
                }
            }
        }
    }
}
