FROM registry.access.redhat.com/ubi9/ubi-minimal:latest AS builder

RUN microdnf install -y --setopt=install_weak_deps=0 --nodocs \
        python3.12 python3.12-pip python3.12-devel gcc \
    && microdnf clean all

WORKDIR /build
COPY requirements.txt .
RUN python3.12 -m venv /venv \
    && /venv/bin/pip install --no-cache-dir --upgrade pip \
    && /venv/bin/pip install --no-cache-dir -r requirements.txt \
    && find /venv -type d -name '__pycache__' -prune -exec rm -rf {} + \
    && rm -rf /venv/lib/python3.12/site-packages/pip* \
              /venv/lib/python3.12/site-packages/setuptools* \
              /venv/lib/python3.12/site-packages/wheel* \
              /venv/bin/pip*

FROM registry.access.redhat.com/ubi9/ubi-minimal:latest

RUN microdnf install -y --setopt=install_weak_deps=0 --nodocs \
        python3.12 shadow-utils \
    && microdnf clean all \
    && useradd --uid 1001 --create-home --shell /sbin/nologin appuser \
    && microdnf remove -y shadow-utils \
    && rm -rf /var/cache/dnf /var/cache/yum

# DISA STIG (RHEL9 SCAP profile) remediation — see docs/adr/0003-base-image.md
# and docs/evidence/phase2-openscap-*.html for the before/after scan reports.
# (Note: this image has no PAM stack / su binary at all — pam_wheel-for-su
# is not applicable here; see the ADR for why that finding only appeared
# during scanning, not in the shipped image.)
RUN sed -i 's/\[ `umask` -eq 0 \] && umask 022/[ `umask` -eq 0 ] \&\& umask 077/' /etc/bashrc \
    && echo 'umask 077' >> /etc/profile \
    && chmod 0640 /root/.bashrc /root/.bash_profile /root/.bash_logout /root/.cshrc /root/.tcshrc \
    && mkdir -p /etc/tmpfiles.d \
    && printf '%s\n' \
        'C /root/.bash_logout 600 root root - /usr/share/rootfiles/.bash_logout' \
        'C /root/.bash_profile 600 root root - /usr/share/rootfiles/.bash_profile' \
        'C /root/.bashrc 600 root root - /usr/share/rootfiles/.bashrc' \
        'C /root/.cshrc 600 root root - /usr/share/rootfiles/.cshrc' \
        'C /root/.tcshrc 600 root root - /usr/share/rootfiles/.tcshrc' \
        > /etc/tmpfiles.d/rootfiles.conf

WORKDIR /app
COPY --from=builder /venv /venv
COPY app ./app

ENV PATH="/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    DATABASE_URL="sqlite:////tmp/readiness.db" \
    LOG_LEVEL="INFO" \
    PORT=8000

USER 1001
EXPOSE 8000

CMD ["python3.12", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
