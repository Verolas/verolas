<#import "template.ftl" as layout>
<#import "register-commons.ftl" as registerCommons>
<@layout.registrationLayout displayMessage=messagesPerField.exists('global') displayRequiredFields=false; section>
    <#if section = "header">
        <h1 id="kc-page-title">Create your Verolas account</h1>
        <p class="verolas-subtitle">Get your firm onto the vertical AI platform for civil engineering.</p>
    <#elseif section = "form">
        <form id="kc-register-form" class="form-horizontal" action="${url.registrationAction}" method="post">
            <@registerCommons.userProfileFormFields; callback, attribute>
                <#if callback = "afterField">
                    <#-- render password fields just under the username or email -->
                    <#if passwordRequired?? && (attribute.name == 'username' || (attribute.name == 'email' && realm.registrationEmailAsUsername))>
                        <div class="form-group">
                            <label for="password" class="control-label">${msg("password")} <span class="required">*</span></label>
                            <input type="password" id="password" class="pf-v5-c-form-control" name="password" autocomplete="new-password" aria-invalid="<#if messagesPerField.existsError('password','password-confirm')>true</#if>" />
                            <#if messagesPerField.existsError('password')>
                                <span id="input-error-password" class="pf-v5-c-form__helper-text pf-m-error" aria-live="polite">${kcSanitize(messagesPerField.get('password'))?no_esc}</span>
                            </#if>
                        </div>

                        <div class="form-group">
                            <label for="password-confirm" class="control-label">${msg("passwordConfirm")} <span class="required">*</span></label>
                            <input type="password" id="password-confirm" class="pf-v5-c-form-control" name="password-confirm" aria-invalid="<#if messagesPerField.existsError('password-confirm')>true</#if>" />
                            <#if messagesPerField.existsError('password-confirm')>
                                <span id="input-error-password-confirm" class="pf-v5-c-form__helper-text pf-m-error" aria-live="polite">${kcSanitize(messagesPerField.get('password-confirm'))?no_esc}</span>
                            </#if>
                        </div>
                    </#if>
                </#if>
            </@registerCommons.userProfileFormFields>

            <#if recaptchaRequired??>
                <div class="form-group">
                    <div class="g-recaptcha" data-size="compact" data-sitekey="${recaptchaSiteKey}"></div>
                </div>
            </#if>

            <div class="form-group" id="kc-form-buttons">
                <input class="pf-v5-c-button pf-m-primary" type="submit" value="${msg("doRegister")}"/>
            </div>
        </form>
    <#elseif section = "socialProviders">
        <#if realm.password && social.providers?? && social.providers?has_content>
            <div class="verolas-divider">or</div>
            <div id="kc-social-providers">
                <ul>
                    <#list social.providers as p>
                        <li>
                            <a id="social-${p.alias}" class="pf-v5-c-button pf-m-secondary" type="button" href="${p.loginUrl}">
                                <#if p.iconClasses?has_content>
                                    <i class="${p.iconClasses!}" aria-hidden="true"></i>
                                </#if>
                                <span class="kc-social-provider-name">Sign up with ${p.displayName!}</span>
                            </a>
                        </li>
                    </#list>
                </ul>
            </div>
        </#if>
    <#elseif section = "info">
        <div id="kc-registration" class="kc-info">
            <span>Already have an account? <a href="${url.loginUrl}">Sign in</a></span>
        </div>
    </#if>
</@layout.registrationLayout>
