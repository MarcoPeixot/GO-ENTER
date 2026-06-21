# --- build stage ---
FROM golang:1.23-alpine AS build
WORKDIR /src

# Cache dependencies first.
COPY go.mod ./
RUN go mod download || true
COPY . .
RUN go mod tidy
RUN CGO_ENABLED=0 go build -o /out/server ./cmd/server

# --- runtime stage ---
FROM alpine:3.20
RUN adduser -D -u 10001 app
WORKDIR /app
COPY --from=build /out/server /app/server
USER app
EXPOSE 8080
ENTRYPOINT ["/app/server"]
