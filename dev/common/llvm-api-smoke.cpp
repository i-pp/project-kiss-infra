// Environment probe only: this is not an AceIS frontend or a custom backend.
#include <llvm/Config/llvm-config.h>
#include <llvm/IR/IRBuilder.h>
#include <llvm/IR/LegacyPassManager.h>
#include <llvm/IR/Module.h>
#include <llvm/IR/Verifier.h>
#include <llvm/MC/TargetRegistry.h>
#include <llvm/Support/FileSystem.h>
#include <llvm/Support/TargetSelect.h>
#include <llvm/Support/raw_ostream.h>
#include <llvm/Target/TargetMachine.h>
#include <memory>
#include <string>
static_assert(LLVM_VERSION_MAJOR == 21 && LLVM_VERSION_MINOR == 1 && LLVM_VERSION_PATCH == 8);
int main(int argc, char **argv) {
    if (argc != 4) return 2; // architecture, output.o, output.ll
    std::string arch = argv[1];
    // All target dependence is confined to these three selections.
    if (arch != "x86_64" && arch != "aarch64") return 2;
    llvm::Triple triple(arch == "x86_64" ? "x86_64-unknown-linux-gnu" : "aarch64-none-elf");
    std::string cpu = arch == "x86_64" ? "x86-64" : "cortex-a53";
    std::string features = arch == "x86_64" ? "+sse2" : "+strict-align";
    llvm::InitializeAllTargetInfos();
    llvm::InitializeAllTargets();
    llvm::InitializeAllTargetMCs();
    llvm::InitializeAllAsmPrinters();
    std::string error;
    auto target = llvm::TargetRegistry::lookupTarget(triple.str(), error);
    if (!target) { llvm::errs() << error; return 1; }
    llvm::TargetOptions options;
    std::unique_ptr<llvm::TargetMachine> tm(target->createTargetMachine(
        triple.str(), cpu, features, options, llvm::Reloc::Static));
    if (!tm) return 1;
    llvm::LLVMContext context;
    llvm::Module module("environment-validation", context);
    module.setTargetTriple(triple);
    module.setDataLayout(tm->createDataLayout());
    llvm::IRBuilder<> builder(context);
    auto type = llvm::FunctionType::get(builder.getInt64Ty(),
        {builder.getInt64Ty(), builder.getInt64Ty()}, false);
    auto function = llvm::Function::Create(type, llvm::Function::ExternalLinkage, "kiss_add_u64", module);
    builder.SetInsertPoint(llvm::BasicBlock::Create(context, "entry", function));
    builder.CreateRet(builder.CreateAdd(function->getArg(0), function->getArg(1))); // modulo 2^64
    if (llvm::verifyModule(module, &llvm::errs())) return 1;
    std::error_code ec;
    llvm::raw_fd_ostream ir(argv[3], ec);
    if (ec) { llvm::errs() << ec.message(); return 1; }
    module.print(ir, nullptr);
    llvm::raw_fd_ostream object(argv[2], ec, llvm::sys::fs::OF_None);
    if (ec) { llvm::errs() << ec.message(); return 1; }
    llvm::legacy::PassManager pm;
    if (tm->addPassesToEmitFile(pm, object, nullptr, llvm::CodeGenFileType::ObjectFile)) return 1;
    pm.run(module);
    llvm::outs() << "LLVM_API PASS " << triple.str() << " CPU=" << cpu << "\n";
}
