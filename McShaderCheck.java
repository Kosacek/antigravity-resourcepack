import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import static org.lwjgl.util.shaderc.Shaderc.*;

/**
 * Compiles Minecraft's (patched) core item shaders the way the 26.3 client does when it loads
 * a resource pack (GlslCompiler: shaderc to SPIR-V, Vulkan 1.2 GLSL, auto-bound uniforms, the
 * RENDERPEARL_DEPTH_IS_ZERO_TO_ONE macro), for each variant of the item pipelines. Includes are
 * inlined here instead of going through shaderc's include callbacks.
 *
 * Usage: java -cp <client libraries> McShaderCheck <include dir> <shader.vsh> <shader.fsh>
 */
public class McShaderCheck {
    static Path includes;

    static String resolve(String src) throws Exception {
        Matcher m = Pattern.compile("#include <minecraft:([a-z_]+\\.glsl)>").matcher(src);
        StringBuilder out = new StringBuilder();
        while (m.find()) {
            m.appendReplacement(out, Matcher.quoteReplacement(resolve(Files.readString(includes.resolve(m.group(1))))));
        }
        m.appendTail(out);
        return out.toString();
    }

    static boolean compile(long compiler, String src, int kind, List<String> flags, String label) {
        long options = shaderc_compile_options_initialize();
        shaderc_compile_options_set_target_env(options, shaderc_target_env_vulkan, shaderc_env_version_vulkan_1_2);
        shaderc_compile_options_set_auto_bind_uniforms(options, true);
        shaderc_compile_options_set_preserve_bindings(options, false);
        shaderc_compile_options_set_optimization_level(options, shaderc_optimization_level_zero);
        shaderc_compile_options_add_macro_definition(options, "RENDERPEARL_DEPTH_IS_ZERO_TO_ONE", "");
        shaderc_compile_options_add_macro_definition(options, "ALPHA_CUTOUT", "0.1");
        for (String flag : flags) {
            String[] kv = flag.split("=", 2);
            shaderc_compile_options_add_macro_definition(options, kv[0], kv.length > 1 ? kv[1] : "");
        }
        long result = shaderc_compile_into_spv(compiler, src, kind, "minecraft:core/item", "main", options);
        boolean ok = shaderc_result_get_compilation_status(result) == shaderc_compilation_status_success;
        System.out.println((ok ? "ok   " : "FAIL ") + label + (ok ? "" : ":\n" + shaderc_result_get_error_message(result)));
        shaderc_result_release(result);
        shaderc_compile_options_release(options);
        return ok;
    }

    public static void main(String[] args) throws Exception {
        includes = Paths.get(args[0]);
        String vsh = resolve(Files.readString(Paths.get(args[1])));
        String fsh = resolve(Files.readString(Paths.get(args[2])));
        List<List<String>> variants = List.of(List.of(), List.of("GLINT"), List.of("GLINT", "GLINT_SPECIAL"),
                List.of("OIT_ALPHA_ONLY"), List.of("OIT", "OIT_COEFF_COUNT=8", "OIT_WAVELET_RANK=3", "OIT_COEFF_ATTACHMENT_COUNT=2", "OIT_ACCUMULATE"),
                List.of("OIT", "OIT_COEFF_COUNT=4", "OIT_WAVELET_RANK=2", "OIT_COEFF_ATTACHMENT_COUNT=1", "OIT_ACCUMULATE", "OIT_ADDITIVE"),
                List.of("OIT", "OIT_COEFF_COUNT=8", "OIT_WAVELET_RANK=3", "OIT_COEFF_ATTACHMENT_COUNT=2", "OIT_TRANSMITTANCE", "OIT_ALPHA_ONLY"),
                List.of("OIT", "OIT_COEFF_COUNT=8", "OIT_WAVELET_RANK=3", "OIT_COEFF_ATTACHMENT_COUNT=2", "OIT_DEPTH_BOUNDS", "OIT_ALPHA_ONLY"),
                List.of("OIT", "OIT_COEFF_COUNT=8", "OIT_WAVELET_RANK=3", "OIT_COEFF_ATTACHMENT_COUNT=2", "OIT_ACCUMULATE", "GLINT", "GLINT_SPECIAL"));
        long compiler = shaderc_compiler_initialize();
        boolean ok = true;
        for (List<String> flags : variants) {
            ok &= compile(compiler, vsh, shaderc_vertex_shader, flags, "vsh " + flags);
            ok &= compile(compiler, fsh, shaderc_fragment_shader, flags, "fsh " + flags);
        }
        shaderc_compiler_release(compiler);
        System.exit(ok ? 0 : 1);
    }
}
