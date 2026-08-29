# Kubernetes Skill - Testing
#
# Usage:
#   make test      # Run all tests
#   make clean     # Remove test resources

NAMESPACE := k8s-skill-test
DEPLOYMENT := k8s-skill-test

.PHONY: all test clean install status help

help:
	@echo "Kubernetes Skill Test Commands:"
	@echo "  make test    - Run all tests (install, verify, clean)"
	@echo "  make clean   - Remove test resources"
	@echo "  make install - Deploy test manifests"
	@echo "  make status  - Show current status"

# === Full Test ===

test: install wait-ready verify clean
	@echo "✓ All Kubernetes skill tests passed"

# === Install ===

install: namespace deploy
	@echo "  ✓ Test deployment installed"

namespace:
	@kubectl create namespace $(NAMESPACE) --dry-run=client -o yaml | kubectl apply -f -

deploy:
	@echo "Deploying test manifests..."
	@kubectl apply -f manifests/test-deployment.yaml -n $(NAMESPACE)

# === Wait ===

wait-ready:
	@echo "Waiting for deployment..."
	@kubectl wait deployment/$(DEPLOYMENT) --for=condition=Available --timeout=120s -n $(NAMESPACE)
	@echo "  ✓ Deployment ready"

# === Verify ===

verify: verify-pods verify-security verify-service
	@echo "  ✓ All verifications passed"

verify-pods:
	@echo "Verifying pods..."
	@kubectl get pods -n $(NAMESPACE) -l app.kubernetes.io/name=$(DEPLOYMENT) -o jsonpath='{.items[0].status.phase}' | grep -q Running
	@echo "    ✓ Pod is Running"

verify-security:
	@echo "Verifying security context..."
	@kubectl get pod -n $(NAMESPACE) -l app.kubernetes.io/name=$(DEPLOYMENT) -o jsonpath='{.items[0].spec.securityContext.runAsNonRoot}' | grep -q true
	@echo "    ✓ runAsNonRoot: true"
	@kubectl get pod -n $(NAMESPACE) -l app.kubernetes.io/name=$(DEPLOYMENT) -o jsonpath='{.items[0].spec.containers[0].securityContext.readOnlyRootFilesystem}' | grep -q true
	@echo "    ✓ readOnlyRootFilesystem: true"

verify-service:
	@echo "Verifying service endpoints..."
	@kubectl get endpoints $(DEPLOYMENT) -n $(NAMESPACE) -o jsonpath='{.subsets[0].addresses[0].ip}' | grep -qE '[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+'
	@echo "    ✓ Service has endpoints"

# === Status ===

status:
	@echo "=== Kubernetes Skill Test Status ==="
	@kubectl get deployment,pod,svc,endpoints -n $(NAMESPACE) 2>/dev/null || echo "No test resources found"

# === Cleanup ===

clean:
	@echo "Cleaning up..."
	@kubectl delete namespace $(NAMESPACE) --ignore-not-found --wait=false
	@echo "  ✓ Cleanup complete"
