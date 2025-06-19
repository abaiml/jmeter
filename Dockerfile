FROM python:3.10-slim

# Install required system packages
RUN apt-get update && \
    apt-get install -y curl unzip ca-certificates && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Java 21 from Adoptium
ENV JAVA_VERSION=21
RUN curl -fsSL https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.3%2B9/OpenJDK21U-jdk_x64_linux_hotspot_21.0.3_9.tar.gz \
    | tar -xz -C /opt/ && \
    ln -s /opt/jdk-21.0.3+9 /opt/java

ENV JAVA_HOME=/opt/java
ENV PATH="${PATH}:${JAVA_HOME}/bin"

# Install JMeter 5.6.3
ENV JMETER_VERSION=5.6.3
RUN curl -sL https://archive.apache.org/dist/jmeter/binaries/apache-jmeter-${JMETER_VERSION}.tgz \
    | tar -xz -C /opt/ && \
    ln -s /opt/apache-jmeter-${JMETER_VERSION} /opt/jmeter

ENV JMETER_HOME=/opt/jmeter
ENV PATH="${PATH}:${JMETER_HOME}/bin"

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app source code
COPY . .

# Expose port
EXPOSE 5000

# Run the app with Gunicorn
CMD ["gunicorn", "--workers=4", "--threads=2", "--timeout=60", "-b", "0.0.0.0:5000", "app:app"]

