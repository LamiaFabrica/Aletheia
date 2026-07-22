#pragma once

#include <stdexcept>
#include <string>
#include <map>
#include <chrono>

// Mimics the strict PsiForceDB Yorkshire Standards error hierarchy
// in the standalone CODEX project.

namespace PsiForceDB {
namespace Error {

enum ErrorSeverity {
    DEBUG = 0,
    INFO = 1,
    WARNING = 2,
    ERROR = 3,
    CRITICAL = 4,
    FATAL = 5
};

struct ErrorCode {
    int category;
    int code;
    ErrorSeverity severity;
    const char* message;
    const char* description;
};

// Standard error codes used by Codex Engine
constexpr ErrorCode SYS_IO_ERROR{4, 520, ERROR, "I/O error", "An input/output error occurred"};
constexpr ErrorCode PROTO_INVALID_MESSAGE{5, 601, ERROR, "Invalid protocol message", "Message does not conform to specification"};

struct ErrorContext {
    std::string file_path;
    std::map<std::string, std::string> additional_data;
};

class PsiForceDBException : public std::runtime_error {
public:
    PsiForceDBException(const std::string& msg, const ErrorContext& ctx = {}) 
        : std::runtime_error(msg), context_(ctx) {}
    
    const ErrorContext& getContext() const { return context_; }
private:
    ErrorContext context_;
};

class SystemException : public PsiForceDBException {
public:
    SystemException(const ErrorCode& /*code*/, const std::string& msg)
        : PsiForceDBException(msg) {}
};

class ProtocolException : public PsiForceDBException {
public:
    ProtocolException(const ErrorCode& /*code*/, const std::string& msg)
        : PsiForceDBException(msg) {}
};

class FileNotFoundException : public PsiForceDBException {
public:
    FileNotFoundException(const std::string& msg, ErrorContext ctx = {}, const std::string& path = "")
        : PsiForceDBException(msg, (ctx.file_path = path, ctx)) {}
};

class ComponentInitializationException : public PsiForceDBException {
public:
    ComponentInitializationException(const std::string& msg, const ErrorContext& ctx = {}, const std::string& /*component*/ = "")
        : PsiForceDBException(msg, ctx) {}
};

} // namespace Error
} // namespace PsiForceDB
