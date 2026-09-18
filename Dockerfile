# Saved as UTF-8 WITHOUT a byte order mark. The previous Dockerfile began with
# the BOM bytes EF BB BF, which made docker build fail on "unknown instruction".

FROM maven:3.9-eclipse-temurin-17 AS build
WORKDIR /app
# Dependencies resolve in their own layer so a code change does not re-download
# the world on every build.
COPY pom.xml .
RUN mvn -B dependency:go-offline
COPY src ./src
RUN mvn -B clean package -DskipTests

FROM eclipse-temurin:17-jre
WORKDIR /app
RUN useradd --system --create-home --uid 10001 studyvault
COPY --from=build /app/target/studyvault.jar app.jar
USER studyvault
EXPOSE 8080
# Without MaxRAMPercentage the JVM sizes its heap from the host, not the
# container, and gets killed on small free tiers.
ENTRYPOINT ["java", "-XX:MaxRAMPercentage=75.0", "-jar", "/app/app.jar"]
