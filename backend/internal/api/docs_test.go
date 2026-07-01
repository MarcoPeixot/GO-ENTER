package api

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"
)

func TestRegisterOpenAPIDocsServesSpec(t *testing.T) {
	gin.SetMode(gin.TestMode)
	router := gin.New()
	RegisterOpenAPIDocs(router)

	recorder := httptest.NewRecorder()
	request := httptest.NewRequest(http.MethodGet, "/openapi.yaml", nil)
	router.ServeHTTP(recorder, request)

	if recorder.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", recorder.Code, recorder.Body.String())
	}
	if contentType := recorder.Header().Get("Content-Type"); !strings.Contains(contentType, "application/yaml") {
		t.Fatalf("expected YAML content type, got %q", contentType)
	}

	body := recorder.Body.String()
	for _, expected := range []string{
		"openapi: 3.0.3",
		"/health:",
		"/documents:",
		"multipart/form-data",
		"/documents/{id}/matches:",
	} {
		if !strings.Contains(body, expected) {
			t.Fatalf("expected OpenAPI spec to contain %q", expected)
		}
	}
}

func TestRegisterOpenAPIDocsServesSwaggerUI(t *testing.T) {
	gin.SetMode(gin.TestMode)
	router := gin.New()
	RegisterOpenAPIDocs(router)

	for _, path := range []string{"/swagger", "/swagger/index.html"} {
		recorder := httptest.NewRecorder()
		request := httptest.NewRequest(http.MethodGet, path, nil)
		router.ServeHTTP(recorder, request)

		if recorder.Code != http.StatusOK {
			t.Fatalf("expected 200 for %s, got %d: %s", path, recorder.Code, recorder.Body.String())
		}
		if contentType := recorder.Header().Get("Content-Type"); !strings.Contains(contentType, "text/html") {
			t.Fatalf("expected HTML content type for %s, got %q", path, contentType)
		}

		body := recorder.Body.String()
		for _, expected := range []string{"SwaggerUIBundle", "/openapi.yaml"} {
			if !strings.Contains(body, expected) {
				t.Fatalf("expected Swagger UI for %s to contain %q", path, expected)
			}
		}
	}
}
