<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=!messagesPerField.existsError('username','password') displayInfo=realm.password && realm.registrationAllowed && !registrationDisabled??; section>
    <#if section = "header">
        <h1 id="kc-page-title">Sign in to Verolas</h1>
        <p class="verolas-subtitle">Continue to your firm's workspace.</p>
    <#elseif section = "form">
        <div id="kc-form">
            <div id="kc-form-wrapper">
                <#if realm.password>
                    <form id="kc-form-login" onsubmit="login.disabled = true; return true;" action="${url.loginAction}" method="post">
                        <#if !usernameHidden??>
                            <div class="form-group">
                                <label for="username" class="control-label"><#if !realm.loginWithEmailAllowed>${msg("username")}<#elseif !realm.registrationEmailAsUsername>${msg("usernameOrEmail")}<#else>${msg("email")}</#if></label>
                                <input tabindex="1" id="username" class="pf-v5-c-form-control" name="username" value="${(login.username!'')}" type="text" autofocus autocomplete="off" aria-invalid="<#if messagesPerField.existsError('username','password')>true</#if>" />
                                <#if messagesPerField.existsError('username','password')>
                                    <span id="input-error" class="pf-v5-c-form__helper-text pf-m-error" aria-live="polite">${kcSanitize(messagesPerField.getFirstError('username','password'))?no_esc}</span>
                                </#if>
                            </div>
                        </#if>

                        <div class="form-group">
                            <label for="password" class="control-label">${msg("password")}</label>
                            <input tabindex="2" id="password" class="pf-v5-c-form-control" name="password" type="password" autocomplete="current-password" aria-invalid="<#if messagesPerField.existsError('username','password')>true</#if>" />
                        </div>

                        <div class="form-group" id="kc-form-options">
                            <div class="checkbox">
                                <#if realm.rememberMe && !usernameHidden??>
                                    <label>
                                        <#if login.rememberMe??>
                                            <input tabindex="3" id="rememberMe" name="rememberMe" type="checkbox" checked> ${msg("rememberMe")}
                                        <#else>
                                            <input tabindex="3" id="rememberMe" name="rememberMe" type="checkbox"> ${msg("rememberMe")}
                                        </#if>
                                    </label>
                                </#if>
                            </div>
                            <#if realm.resetPasswordAllowed>
                                <span><a tabindex="5" href="${url.loginResetCredentialsUrl}">${msg("doForgotPassword")}</a></span>
                            </#if>
                        </div>

                        <div id="kc-form-buttons" class="form-group">
                            <input tabindex="4" class="pf-v5-c-button pf-m-primary" name="login" id="kc-login" type="submit" value="${msg("doLogIn")}"/>
                        </div>
                    </form>
                </#if>
            </div>
        </div>
    <#elseif section = "socialProviders">
        <#if realm.password && social.providers?? && social.providers?has_content>
            <div class="verolas-divider">or</div>
            <div id="kc-social-providers" class="pf-v5-c-login__main-footer-links">
                <ul>
                    <#list social.providers as p>
                        <li>
                            <a id="social-${p.alias}" class="pf-v5-c-button pf-m-secondary" type="button" href="${p.loginUrl}">
                                <#if p.iconClasses?has_content>
                                    <i class="${p.iconClasses!}" aria-hidden="true"></i>
                                </#if>
                                <span class="kc-social-provider-name">Continue with ${p.displayName!}</span>
                            </a>
                        </li>
                    </#list>
                </ul>
            </div>
        </#if>
    <#elseif section = "info">
        <#if realm.password && realm.registrationAllowed && !registrationDisabled??>
            <div id="kc-registration-container">
                <div id="kc-registration">
                    <span>${msg("noAccount")} <a tabindex="6" href="${url.registrationUrl}">${msg("doRegister")}</a></span>
                </div>
            </div>
        </#if>
    </#if>
</@layout.registrationLayout>
